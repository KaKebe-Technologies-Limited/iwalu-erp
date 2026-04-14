from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'system-config', views.SystemConfigViewSet, basename='system-config')
router.register(r'approval-thresholds', views.ApprovalThresholdViewSet)
router.register(r'audit-settings', views.AuditSettingViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
