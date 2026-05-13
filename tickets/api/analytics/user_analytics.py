"""User analytics — per-user ticket history and feedback opportunity dashboard."""

from django.db.models import Avg, Count, F, Q
from django.utils import timezone

from tickets.models import Ticket, Feedback
from .base_analytics import ACTIVE_STATUSES, TERMINAL_STATUSES, get_cached


class UserAnalytics:
    """Analytics scoped to a single end-user."""

    @staticmethod
    def for_user(user) -> dict:
        return get_cached(
            f"analytics_user_{user.id}",
            lambda: UserAnalytics._compute(user),
            ttl=60,
        )

    @staticmethod
    def _compute(user) -> dict:
        base_qs = Ticket.objects.filter(raised_by=user)

        # ── Status counters ───────────────────────────────────────────────────
        agg = base_qs.aggregate(
            total=Count("id"),
            open=Count("id", filter=Q(status__in=ACTIVE_STATUSES)),
            closed=Count("id", filter=Q(status__in=TERMINAL_STATUSES)),
            pending=Count("id", filter=Q(status="pending")),
            pending_approval=Count("id", filter=Q(status="pending_approval")),
            escalated=Count("id", filter=Q(escalation_level__gt=0)),
            rejected=Count("id", filter=Q(status="rejected")),
            avg_resolution_duration=Avg(
                F("resolved_at") - F("created_at"),
                filter=Q(status__in=TERMINAL_STATUSES, resolved_at__isnull=False),
            ),
        )

        # ── Recent tickets ────────────────────────────────────────────────────
        recent_tickets = [
            {
                "id": t.id,
                "ticket_no": t.ticket_no,
                "title": t.title,
                "status": t.status,
                "priority": t.priority,
                "campus": t.campus_department.campus.code,
                "department": t.campus_department.department.name,
                "section": t.section.name if t.section else None,
                "assigned_to": (
                    {
                        "id": t.assigned_to.id,
                        "name": (
                            f"{t.assigned_to.first_name} {t.assigned_to.last_name}".strip()
                            or t.assigned_to.username
                        ),
                    }
                    if t.assigned_to else None
                ),
                "service_item": t.service_item.name if t.service_item else None,
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat(),
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "is_overdue": t.is_overdue,
            }
            for t in (
                base_qs
                .select_related(
                    "campus_department__campus",
                    "campus_department__department",
                    "section",
                    "assigned_to",
                    "service_item",
                )
                .order_by("-updated_at")[:15]
            )
        ]

        # ── Feedback opportunity ──────────────────────────────────────────────
        feedback_needed = list(
            base_qs
            .filter(status="resolved")
            .exclude(id__in=Feedback.objects.values("ticket_id"))
            .select_related("section")
            .values("id", "ticket_no", "title", "resolved_at", section_name=F("section__name"))
            .order_by("-resolved_at")[:5]
        )

        # ── Status distribution ───────────────────────────────────────────────
        status_dist = list(
            base_qs.values("status").annotate(count=Count("id")).order_by("-count")
        )

        avg_res = agg.get("avg_resolution_duration")
        avg_res_hours = round(avg_res.total_seconds() / 3600, 2) if avg_res else 0.0

        return {
            "user": {
                "id": user.id,
                "username": user.username,
                "name": f"{user.first_name} {user.last_name}".strip() or user.username,
            },
            "summary": {
                "total": agg["total"] or 0,
                "open": agg["open"] or 0,
                "closed": agg["closed"] or 0,
                "pending": agg["pending"] or 0,
                "pending_approval": agg["pending_approval"] or 0,
                "escalated": agg["escalated"] or 0,
                "rejected": agg["rejected"] or 0,
                "avg_resolution_hours": avg_res_hours,
            },
            "recent_tickets": recent_tickets,
            "feedback_needed": feedback_needed,
            "status_distribution": status_dist,
        }
