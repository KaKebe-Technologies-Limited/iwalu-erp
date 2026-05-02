from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'menu-categories', views.MenuCategoryViewSet)
router.register(r'menu-items', views.MenuItemViewSet)
router.register(r'orders', views.MenuOrderViewSet)
router.register(r'waste-logs', views.WasteLogViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
