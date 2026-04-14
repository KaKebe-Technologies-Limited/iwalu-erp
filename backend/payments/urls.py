from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('config', views.PaymentConfigViewSet, basename='payment-config')
router.register('transactions', views.PaymentTransactionViewSet, basename='payment-transaction')
router.register('', views.PaymentViewSet, basename='payments')

urlpatterns = [
    path('', include(router.urls)),
]
