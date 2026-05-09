from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'boms', views.BillOfMaterialsViewSet)
router.register(r'orders', views.ProductionOrderViewSet)
router.register(r'wip', views.WorkInProgressViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
