from rest_framework import routers
from django.urls import include, path
from .views import *

router = routers.DefaultRouter()
router.register(r'feedback', FeedbackViewSet)
router.register(r'tickets', TicketViewSet)
router.register(r'comments', CommentViewSet)
router.register(r'sections', SectionViewSet)
router.register(r'facilities', FacilityViewSet)
router.register(r'users', UserViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
]