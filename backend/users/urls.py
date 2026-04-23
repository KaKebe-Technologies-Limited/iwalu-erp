from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views
from .social_auth import GoogleLogin, AppleLogin

router = DefaultRouter()
router.register(r'users', views.UserViewSet)

urlpatterns = [
    # Explicit paths must come before the router include so they aren't
    # shadowed by the router's users/<pk>/ pattern.
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/me/', views.current_user, name='current_user'),
    path('auth/me/permissions/', views.current_user_permissions, name='current_user_permissions'),
    path('auth/register/', views.register, name='register'),
    path('auth/social/google/', GoogleLogin.as_view(), name='google_login'),
    path('auth/social/apple/', AppleLogin.as_view(), name='apple_login'),
    path('users/invite/', views.invite_user, name='user-invite'),
    path('users/invitations/', views.list_invitations, name='user-invitations'),
    path('users/accept-invite/', views.accept_invite, name='user-accept-invite'),
    path('', include(router.urls)),
]
