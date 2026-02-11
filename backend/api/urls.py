from django.urls import include, path
from . import views

urlpatterns = [
    path('health/', views.health_check, name='health_check'),
    path('', include('users.urls')),
]