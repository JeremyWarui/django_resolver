"""Admin dashboard — consolidated endpoint for admin dashboard data."""

from django.db.models import Count, Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from tickets.api.analytics.admin_analytics import AdminAnalytics
from tickets.models import Campus, Department, Section, CustomUser


class AdminDashboardView(APIView):
    """GET /api/admin/me/dashboard/

    Consolidated Admin dashboard combining:
    - Admin user info
    - System-wide analytics (overview, overdue tickets)
    - Organisation structure summary (counts)
    - Recent tickets (last 15)

    Permission:
        admin   → full access
        others  → 403

    Query params:
        days    — lookback window for analytics (default: 30, max: 365)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != "admin":
            return Response({"detail": "Admin role required."}, status=403)

        # Parse days parameter
        try:
            days = int(request.query_params.get("days", 30))
            days = max(1, min(days, 365))
        except (TypeError, ValueError):
            days = 30

        # Get admin user info
        admin = request.user
        admin_info = {
            "id": admin.id,
            "username": admin.username,
            "name": f"{admin.first_name} {admin.last_name}".strip() or admin.username,
            "email": admin.email,
        }

        # Get analytics data
        analytics = {
            "system_overview": AdminAnalytics.get_system_overview(),
            "overdue_tickets": AdminAnalytics.get_overdue_tickets(),
        }

        # Get organisation structure counts
        org_summary = {
            "total_sections": Section.objects.count(),
            "total_technicians": CustomUser.objects.filter(role="technician", is_active=True).count(),
            "total_facilities": Section.objects.values("campus_department__campus").distinct().count(),
            "total_campuses": Campus.objects.count(),
            "total_departments": Department.objects.count(),
        }

        return Response({
            "admin": admin_info,
            "analytics": analytics,
            "org_summary": org_summary,
        })
