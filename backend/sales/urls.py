from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'discounts', views.DiscountViewSet)
router.register(r'shifts', views.ShiftViewSet)
router.register(r'sales', views.SaleViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('checkout/', views.checkout, name='checkout'),
]
