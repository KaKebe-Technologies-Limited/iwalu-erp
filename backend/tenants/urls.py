from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'billing/plans', views.SubscriptionPlanViewSet, basename='billing-plans')
router.register(r'billing/subscriptions', views.TenantSubscriptionViewSet, basename='billing-subscriptions')
router.register(r'billing/invoices', views.SubscriptionInvoiceViewSet, basename='billing-invoices')

urlpatterns = [
    path('tenants/register/', views.register_tenant, name='tenant-register'),
    path('tenants/verify-email/', views.verify_tenant_email, name='tenant-verify-email'),
    path('tenants/resend-verification/', views.resend_verification_email, name='tenant-resend-verification'),
    path('', include(router.urls)),
]
