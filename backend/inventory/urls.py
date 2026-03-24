from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'suppliers', views.SupplierViewSet)
router.register(r'outlet-stock', views.OutletStockViewSet)
router.register(r'purchase-orders', views.PurchaseOrderViewSet)
router.register(r'stock-transfers', views.StockTransferViewSet)
router.register(r'stock-audit-log', views.StockAuditLogViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
