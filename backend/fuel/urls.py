from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'fuel/pumps', views.PumpViewSet)
router.register(r'fuel/tanks', views.TankViewSet)
router.register(r'fuel/pump-readings', views.PumpReadingViewSet)
router.register(r'fuel/deliveries', views.FuelDeliveryViewSet)
router.register(r'fuel/reconciliations', views.FuelReconciliationViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('fuel/reports/daily-pump/', views.daily_pump_report, name='fuel-daily-pump-report'),
    path('fuel/reports/variance/', views.variance_report, name='fuel-variance-report'),
    path('fuel/reports/tank-levels/', views.tank_levels_summary, name='fuel-tank-levels'),
]
