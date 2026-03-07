from django.urls import include, path
from . import views

urlpatterns = [
    path('health/', views.health_check, name='health_check'),
    path('', include('users.urls')),
    path('', include('outlets.urls')),
    path('', include('products.urls')),
    path('', include('sales.urls')),
]