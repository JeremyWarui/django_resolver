from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from tickets.serializers import SectionSerializer, FacilitySerializer, TicketSerializer
from tickets.serializers import CommentSerializer, FeedbackSerializer, UserSerializer
from django_filters.rest_framework import DjangoFilterBackend
from tickets.api.services.ticket_services import (
    create_ticket, update_ticket, create_comment, create_feedback
)
from tickets.api.pagination import StandardResultsSetPagination
from tickets.models import Section, Facility, Ticket, Comment, Feedback, CustomUser


# --------------------------------
# SECTION API
# ----------------------------------

class SectionListCreateView(ListCreateAPIView):
    queryset = Section.objects.all()
    serializer_class = SectionSerializer
    pagination_class = StandardResultsSetPagination
    # permission_classes = [IsAuthenticated]


class SectionDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Section.objects.all()
    serializer_class = SectionSerializer
    # permission_classes = [IsAuthenticated]


# --------------------------------
# FACILITY API
# ----------------------------------

class FacilityListCreateView(ListCreateAPIView):
    queryset = Facility.objects.all()
    serializer_class = FacilitySerializer
    pagination_class = StandardResultsSetPagination
    # permission_classes = [IsAuthenticated]


class FacilityDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Facility.objects.all()
    serializer_class = FacilitySerializer
    # permission_classes = [IsAuthenticated]


# --------------------------------
# TICKETS API
# ----------------------------------

class TicketListCreateView(ListCreateAPIView):
    queryset = Ticket.objects.all().order_by('-created_at')
    serializer_class = TicketSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'section', 'assigned_to', 'raised_by']
    # permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        """Delegate ticket creation to service layer """
        create_ticket(serializer, self.request.user)


class TicketDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
    # permission_classes = [IsAuthenticated]

    def perform_update(self, serializer):
        """ delegate ticket update ( assign, update status, etc) """
        update_ticket(serializer, self.request.user)


# --------------------------------
# COMMENTS API
# ----------------------------------

class CommentListCreateView(ListCreateAPIView):
    queryset = Comment.objects.all().order_by('created_at')
    serializer_class = CommentSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['author', 'ticket']
    # permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        ticket_id = self.kwargs.get("ticket_id")
        create_comment(serializer, self.request.user, ticket_id)


# --------------------------------
# FEEDBACK API
# ----------------------------------

class FeedbackListCreateView(ListCreateAPIView):
    queryset = Feedback.objects.all().order_by('-created_at')
    serializer_class = FeedbackSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['rating', 'rated_by', 'ticket']
    # permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        ticket_id = self.kwargs.get("ticket_id")
        create_feedback(serializer, self.request.user, ticket_id)


# --------------------------------
# USERS API
# ----------------------------------

class UserListCreateView(ListCreateAPIView):
    queryset = CustomUser.objects.all().order_by('username')
    serializer_class = UserSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['role', 'sections']
    # permission_classes = [IsAuthenticated]


class UserDetailView(RetrieveUpdateDestroyAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    # permission_classes = [IsAuthenticated]
