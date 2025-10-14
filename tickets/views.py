from django.shortcuts import render
from rest_framework import viewsets, filters
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from .serializers import *
from django_filters.rest_framework import DjangoFilterBackend
from . import services

# Create your views here.

# --------------------------------
# SECTION
# ----------------------------------
class SectionListCreateView(ListCreateAPIView):
    queryset = Section.objects.all()
    serializer_class = SectionSerializer

class SectionDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Section.objects.all()
    serializer_class = SectionSerializer

# --------------------------------
# FACILITY
# ----------------------------------

class FacilityListCreateView(ListCreateAPIView):
    queryset = Facility.objects.all()
    serializer_class = FacilitySerializer

class FacilityDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Facility.objects.all()
    serializer_class = FacilitySerializer

# --------------------------------
# TICKETS
# ----------------------------------

class TicketListCreateView(ListCreateAPIView):
    queryset = Ticket.objects.all().order_by('-created_at')
    serializer_class = TicketSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'section', 'assigned_to', 'raised_by']

    def perform_create(self, serializer):
        """Delegate ticket creation to service layer"""
       services.create_ticket(serializer, self.request.user)

class TicketDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer

    def perform_update(self, serializer):
        """ delegate ticket update ( assign, update status, etc) """
        services.update_ticket(serializer, self.request.user)

# --------------------------------
# COMMENTS
# ----------------------------------

class CommentListCreateView(ListCreateAPIView):
    queryset = Comment.objects.all().order_by('created_at')
    serializer_class = CommentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['author', 'ticket']

    def perform_create(self, serializer):
        # ticket_id = self.request.data.get('ticket_id')
        # services.create_comment(serializer, self.request.user, ticket_id)


# --------------------------------
# FEEDBACK
# ----------------------------------

class FeedbackListCreateView(ListCreateAPIView):
    queryset = Feedback.objects.all().order_by('-created_at')
    serializer_class = FeedbackSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['rating', 'rated_by', 'ticket']

    def perform_create(self, serializer):
        # ticket_id = self.request.data.get('ticket_id')
        # services.create_feedback(serializer, self.request.user, ticket_id)


# --------------------------------
# FEEDBACK
# ----------------------------------

class UserListCreateView(ListCreateAPIView):
    queryset = CustomUser.objects.all().order_by('username')
    serializer_class = UserSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['role']

class UserDetailView(RetrieveUpdateDestroyAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer