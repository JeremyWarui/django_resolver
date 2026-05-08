from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.urls import reverse
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending authentication-related emails."""

    @classmethod
    def send_magic_link(cls, user, magic_link, request=None):
        """
        Send magic link email to user.

        Args:
            user: CustomUser instance
            magic_link: MagicLink instance
            request: HttpRequest instance for building absolute URLs
        """
        try:
            # Build magic link URL
            if request:
                magic_url = request.build_absolute_uri(
                    reverse("magic_link_login", args=[magic_link.token])
                )
            else:
                # Fallback for testing/development
                base_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
                magic_url = f"{base_url}/auth/magic-link/{magic_link.token}"

            # Email context
            context = {
                "user": user,
                "magic_url": magic_url,
                "expiry_minutes": 15,
                "company_name": getattr(settings, "COMPANY_NAME", "Django Resolver"),
            }

            # Render email templates
            html_message = render_to_string("emails/magic_link.html", context)
            plain_message = render_to_string("emails/magic_link.txt", context)

            # Send email
            send_mail(
                subject=f"Your secure login link for {context['company_name']}",
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )

            logger.info(f"Magic link email sent to {user.email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send magic link email to {user.email}: {str(e)}")
            return False

    @classmethod
    def send_login_notification(cls, user, session_info):
        """
        Send login notification email for security.

        Args:
            user: CustomUser instance
            session_info: LoginSession instance
        """
        try:
            context = {
                "user": user,
                "login_method": session_info.login_method,
                "login_time": session_info.created_at,
                "ip_address": session_info.ip_address,
                "user_agent": session_info.user_agent,
                "company_name": getattr(settings, "COMPANY_NAME", "Django Resolver"),
            }

            # Render email templates
            html_message = render_to_string("emails/login_notification.html", context)
            plain_message = render_to_string("emails/login_notification.txt", context)

            # Send email
            send_mail(
                subject=f"New login to your {context['company_name']} account",
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=True,  # Don't fail login if notification fails
            )

            logger.info(f"Login notification sent to {user.email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send login notification to {user.email}: {str(e)}")
            return False

    # -------------------------------------------------------------------------
    # TICKET LIFECYCLE NOTIFICATIONS
    # -------------------------------------------------------------------------

    @classmethod
    def _ticket_url(cls, ticket) -> str:
        base = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
        return f"{base}/tickets/{ticket.id}"

    @classmethod
    def _company_name(cls) -> str:
        return getattr(settings, "COMPANY_NAME", "Resolver")

    @classmethod
    def send_ticket_assigned(cls, ticket, technician) -> bool:
        """Notify the assigned technician that a ticket has been given to them."""
        if not technician.email:
            return False
        try:
            context = {
                "ticket": ticket,
                "technician": technician,
                "ticket_url": cls._ticket_url(ticket),
                "company_name": cls._company_name(),
            }
            message = render_to_string("emails/ticket_assigned.txt", context)
            send_mail(
                subject=f"[{cls._company_name()}] Ticket {ticket.ticket_no} assigned to you",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[technician.email],
                fail_silently=True,
            )
            logger.info(f"Assignment notification sent to {technician.email} for {ticket.ticket_no}")
            return True
        except Exception as e:
            logger.error(f"Failed to send assignment notification for {ticket.ticket_no}: {e}")
            return False

    @classmethod
    def send_ticket_resolved(cls, ticket) -> bool:
        """Notify the requester that their ticket has been resolved."""
        requester = ticket.raised_by
        if not requester.email:
            return False
        try:
            base = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
            context = {
                "ticket": ticket,
                "requester": requester,
                "ticket_url": cls._ticket_url(ticket),
                "feedback_url": f"{base}/tickets/{ticket.id}/feedback",
                "company_name": cls._company_name(),
            }
            message = render_to_string("emails/ticket_resolved.txt", context)
            send_mail(
                subject=f"[{cls._company_name()}] Your request {ticket.ticket_no} has been resolved",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[requester.email],
                fail_silently=True,
            )
            logger.info(f"Resolved notification sent to {requester.email} for {ticket.ticket_no}")
            return True
        except Exception as e:
            logger.error(f"Failed to send resolved notification for {ticket.ticket_no}: {e}")
            return False

    @classmethod
    def send_ticket_rejected(cls, ticket, reason: str) -> bool:
        """Notify the requester that their ticket has been rejected, with the reason."""
        requester = ticket.raised_by
        if not requester.email:
            return False
        try:
            context = {
                "ticket": ticket,
                "requester": requester,
                "reason": reason,
                "company_name": cls._company_name(),
            }
            message = render_to_string("emails/ticket_rejected.txt", context)
            send_mail(
                subject=f"[{cls._company_name()}] Your request {ticket.ticket_no} has been declined",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[requester.email],
                fail_silently=True,
            )
            logger.info(f"Rejection notification sent to {requester.email} for {ticket.ticket_no}")
            return True
        except Exception as e:
            logger.error(f"Failed to send rejection notification for {ticket.ticket_no}: {e}")
            return False

    @classmethod
    def send_ticket_pending_approval(cls, ticket) -> bool:
        """Notify the department HOD that a ticket is awaiting their approval."""
        try:
            hod = (
                ticket.section.department.head_of_department
                if ticket.section and ticket.section.department
                else None
            )
            if not hod or not hod.email:
                logger.warning(
                    f"No HOD email found for {ticket.ticket_no}; skipping approval notification"
                )
                return False

            context = {
                "ticket": ticket,
                "approver": hod,
                "ticket_url": cls._ticket_url(ticket),
                "company_name": cls._company_name(),
            }
            message = render_to_string("emails/ticket_pending_approval.txt", context)
            send_mail(
                subject=f"[{cls._company_name()}] Approval required: {ticket.ticket_no}",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[hod.email],
                fail_silently=True,
            )
            logger.info(f"Approval notification sent to {hod.email} for {ticket.ticket_no}")
            return True
        except Exception as e:
            logger.error(f"Failed to send approval notification for {ticket.ticket_no}: {e}")
            return False
