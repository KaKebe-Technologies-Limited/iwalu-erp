from rest_framework.routers import DefaultRouter
from .views import (
    ProjectViewSet, ProjectTaskViewSet,
    ProjectExpenseViewSet, ProjectTimeEntryViewSet
)

router = DefaultRouter()
router.register(r'projects', ProjectViewSet)
router.register(r'tasks', ProjectTaskViewSet)
router.register(r'expenses', ProjectExpenseViewSet)
router.register(r'time-entries', ProjectTimeEntryViewSet)

urlpatterns = router.urls
