from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'fiscalization/config', views.EfrisConfigViewSet,
                basename='efris-config')
router.register(r'fiscalization/invoices', views.FiscalInvoiceViewSet,
                basename='fiscal-invoice')

urlpatterns = [
    path('', include(router.urls)),
]
