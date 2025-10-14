# tickets/urls.py
from django.urls import path
from .views import (
    SectionListCreateView, SectionDetailView,
    FacilityListCreateView, FacilityDetailView,
    TicketListCreateView, TicketDetailView,
    CommentListCreateView,
    FeedbackListCreateView,
    UserListCreateView, UserDetailView,
)

urlpatterns = [
    # SECTION
    path('sections/', SectionListCreateView.as_view(), name='section-list'),
    path('sections/<int:pk>/', SectionDetailView.as_view(), name='section-detail'),

    # FACILITY
    path('facilities/', FacilityListCreateView.as_view(), name='facility-list'),
    path('facilities/<int:pk>/', FacilityDetailView.as_view(),
         name='facility-detail'),

    # TICKET
    path('tickets/', TicketListCreateView.as_view(), name='ticket-list'),
    path('tickets/<int:pk>/', TicketDetailView.as_view(), name='ticket-detail'),

    # COMMENT
    path('comments/', CommentListCreateView.as_view(), name='comment-list'),

    # FEEDBACK
    path('feedback/', FeedbackListCreateView.as_view(), name='feedback-list'),

    # USER
    path('users/', UserListCreateView.as_view(), name='user-list'),
    path('users/<int:pk>/', UserDetailView.as_view(), name='user-detail'),

    # NESTED TICKET RESOURCES
    path('tickets/<int:ticket_id>/comments/',
         CommentListCreateView.as_view(), name='ticket-comments'),
    path('tickets/<int:ticket_id>/feedback/',
         FeedbackListCreateView.as_view(), name='ticket-feedback'),
]
