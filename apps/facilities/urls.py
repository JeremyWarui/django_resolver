from rest_framework.routers import DefaultRouter

from apps.facilities.views import FacilityTypeViewSet, FacilityViewSet

router = DefaultRouter()
router.register("facility-types", FacilityTypeViewSet, basename="facilitytype")
router.register("facilities", FacilityViewSet, basename="facility")

urlpatterns = router.urls
