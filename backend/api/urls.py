from django.urls import include, path
from . import views

urlpatterns = [
    path('health/', views.health_check, name='health_check'),
    path('', include('tenants.urls')),
    path('', include('users.urls')),
    path('', include('outlets.urls')),
    path('', include('products.urls')),
    path('', include('sales.urls')),
    path('', include('inventory.urls')),
    path('', include('reports.urls')),
    path('', include('finance.urls')),
    path('', include('hr.urls')),
    path('', include('fuel.urls')),
    path('', include('notifications.urls')),
    path('', include('system_config.urls')),
    path('', include('fiscalization.urls')),
    path('payments/', include('payments.urls')),
    path('', include('approvals.urls')),
]