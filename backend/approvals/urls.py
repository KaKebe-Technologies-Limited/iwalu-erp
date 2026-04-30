from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ApprovalPolicyViewSet, ApprovalRequestViewSet

router = DefaultRouter()
router.register(r'approval-policies', ApprovalPolicyViewSet)
router.register(r'approvals', ApprovalRequestViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
