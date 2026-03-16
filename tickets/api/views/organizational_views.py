"""
Enhanced organizational API views for Phase 6 integration.

These views provide comprehensive endpoints for:
- Organizational ticket listing with scope-aware filtering
- Technician assignment with validation
- Unified analytics dashboard
"""

from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from tickets.models import Section, Ticket, CustomUser
from tickets.serializers import TicketListSerializer, TicketSerializer, UserSerializer
from tickets.api.permissions import (
    IsWithinOrganizationalScope,
    CanAssignTickets,
    CanEscalateTickets,
    CanViewAnalytics,
)
from tickets.api.services import OrganizationalTicketService
from tickets.api.analytics.organizational_analytics import OrganizationalAnalytics
from tickets.pagination import TicketPagination


class OrganizationalTicketListView(ListAPIView):
    """
    List tickets within user's organizational scope.

    Supports filtering by:
    - status: open, assigned, in_progress, pending, resolved, closed, escalated
    - section_id: specific section
    - assigned_to_id: assigned technician
    - escalation_level: 0 (none), 1 (section_head), 2 (hod)
    - is_overdue: boolean (tickets >7 days old)

    Respects organizational hierarchy:
    - Admin: sees all tickets
    - Director: sees organization-wide tickets
    - HOD: sees campus-level tickets
    - Section Head: sees department-level tickets
    - Technician/User: sees section-level tickets
    """

    serializer_class = TicketListSerializer
    permission_classes = [IsAuthenticated, IsWithinOrganizationalScope]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    pagination_class = TicketPagination

    filterset_fields = ['status', 'escalation_level']
    ordering_fields = ['created_at', 'updated_at', 'status']
    ordering = ['-updated_at']

    def get_queryset(self):
        """
        Return tickets accessible to user based on organizational role.
        Uses service layer for consistent scope filtering.
        """
        return OrganizationalTicketService.get_accessible_tickets(
            self.request.user
        )

    def get_serializer_context(self):
        """Add request context for serializer"""
        context = super().get_serializer_context()
        context['skip_available_technicians'] = True
        return context


class AssignableUsersView(ListAPIView):
    """
    Get technicians that can be assigned tickets in a specific section.

    Query Parameters:
    - section_id: Required. ID of the section to get technicians for

    Returns:
    - List of technician users who are:
      1. Active and have 'technician' role
      2. Associated with the specified section
      3. Accessible within the user's organizational scope

    Example: GET /api/assignable-users/?section_id=5
    """

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, CanAssignTickets]

    def get_queryset(self):
        """
        Get technicians assignable to the requested section.
        Validates user can assign in this section per organizational scope.
        """
        section_id = self.request.query_params.get('section_id')

        if not section_id:
            return CustomUser.objects.none()

        try:
            section = Section.objects.select_related(
                'department',
                'department__campus',
                'department__campus__organization'
            ).get(id=section_id)
        except Section.DoesNotExist:
            return CustomUser.objects.none()

        user = self.request.user

        # Validate user can assign in this section using service layer
        try:
            if not OrganizationalTicketService._can_user_access_section(user, section):
                return CustomUser.objects.none()
        except (PermissionDenied, ValidationError):
            return CustomUser.objects.none()

        # Return active technicians assigned to this section
        return CustomUser.objects.filter(
            role='technician',
            sections=section,
            is_active=True
        ).order_by('first_name', 'last_name').select_related('primary_department')


class OrganizationalAnalyticsView(APIView):
    """
    Unified analytics endpoint that returns role-specific dashboards.

    Returns different dashboard data based on user's organizational role:
    - Director: Organization-wide metrics and alerts
    - HOD: Campus-level performance and escalations
    - Section Head: Department efficiency and technician performance

    GET /api/analytics/organizational/?days=30&timeframe=month

    Query Parameters:
    - days: Number of days to include in analysis (default: 30)
    - timeframe: 'day', 'week', 'month' for grouping (default: 'month')
    """

    permission_classes = [IsAuthenticated, CanViewAnalytics]

    def get(self, request):
        """
        Return analytics dashboard data based on user's role.
        Falls back to limited data if insufficient permissions.
        """
        user = request.user
        days = int(request.query_params.get('days', 30))
        timeframe = request.query_params.get('timeframe', 'month')

        try:
            if user.role == 'director':
                data = OrganizationalAnalytics.director_dashboard(
                    user,
                    days=days
                )
            elif user.role == 'hod':
                data = OrganizationalAnalytics.hod_dashboard(
                    user,
                    days=days
                )
            elif user.role == 'section_head':
                data = OrganizationalAnalytics.section_head_dashboard(
                    user,
                    days=days
                )
            else:
                return Response(
                    {'error': 'User role does not have access to analytics dashboard'},
                    status=status.HTTP_403_FORBIDDEN
                )

            return Response(data)

        except Exception as e:
            return Response(
                {'error': f'Failed to generate analytics: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class EscalateTicketView(APIView):
    """
    Endpoint for manually escalating tickets with validation.

    POST /api/tickets/{ticket_id}/escalate-manual/
    {
        "reason": "Issue requires higher-level attention"
    }

    Escalation must follow organizational hierarchy:
    - Open/Assigned/In Progress → Escalate to Section Head
    - Section Head escalation → Escalate to HOD
    - Cannot escalate beyond HOD
    """

    permission_classes = [IsAuthenticated, CanEscalateTickets]

    def post(self, request, ticket_id):
        """Handle manual ticket escalation"""
        try:
            ticket = Ticket.objects.select_related(
                'section',
                'section__department',
                'section__department__campus',
                'escalated_to'
            ).get(id=ticket_id)

        except Ticket.DoesNotExist:
            return Response(
                {'error': 'Ticket not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Validate user can escalate this ticket
        try:
            OrganizationalTicketService._can_user_access_section(
                request.user, ticket.section)
        except (PermissionDenied, ValidationError) as e:
            return Response(
                {'error': f'Cannot escalate tickets outside your scope: {str(e)}'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get escalation reason
        reason = request.data.get('reason', '')
        if not reason:
            return Response(
                {'error': 'Escalation reason is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Perform escalation
        try:
            updated_ticket = OrganizationalTicketService.escalate_ticket(
                ticket=ticket,
                escalated_by=request.user,
                reason=reason,
                manual=True
            )

            return Response(
                {
                    'success': True,
                    'message': 'Ticket escalated successfully',
                    'ticket_no': updated_ticket.ticket_no,
                    'escalation_level': updated_ticket.escalation_level,
                    'escalated_to': (
                        f"{updated_ticket.escalated_to.first_name} "
                        f"{updated_ticket.escalated_to.last_name}"
                        if updated_ticket.escalated_to else None
                    ),
                    'next_escalation_due': updated_ticket.next_escalation_due
                },
                status=status.HTTP_200_OK
            )

        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Escalation failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
