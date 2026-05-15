from django.urls import path

from .auth import MobileTokenObtainPairView, MobileTokenRefreshView
from .views import MobileSyncView, ShiftStartDataView

urlpatterns = [
    path('auth/login/', MobileTokenObtainPairView.as_view(), name='mobile-login'),
    path('auth/refresh/', MobileTokenRefreshView.as_view(), name='mobile-refresh'),
    path('shift-start-data/', ShiftStartDataView.as_view(), name='mobile-shift-start-data'),
    path('sync/', MobileSyncView.as_view(), name='mobile-sync'),
]
