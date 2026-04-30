from django.urls import path
from . import views

urlpatterns = [
    path('tenants/register/', views.register_tenant, name='tenant-register'),
]
