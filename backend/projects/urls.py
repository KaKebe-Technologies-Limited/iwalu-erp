from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import (
    ProjectViewSet, ProjectTaskViewSet,
    ProjectExpenseViewSet, ProjectTimeEntryViewSet
)

router = DefaultRouter()
router.register(r'tasks', ProjectTaskViewSet, basename='projecttask')
router.register(r'expenses', ProjectExpenseViewSet, basename='projectexpense')
router.register(r'time-entries', ProjectTimeEntryViewSet, basename='projecttimeentry')
router.register(r'', ProjectViewSet, basename='project')

urlpatterns = [
    path('', include(router.urls)),
]
