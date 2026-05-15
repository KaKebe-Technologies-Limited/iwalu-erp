from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework import serializers as drf_serializers


class MobileTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extends the standard JWT serializer to embed 'client' and 'role' claims
    and reject login for roles other than cashier and attendant.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['client'] = 'mobile'
        token['role'] = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        allowed_roles = ('cashier', 'attendant')
        if user.role not in allowed_roles:
            raise drf_serializers.ValidationError(
                "Mobile access restricted to cashier and attendant roles."
            )
        return data


class MobileLoginThrottle(AnonRateThrottle):
    scope = 'mobile-login'


class MobileTokenObtainPairView(TokenObtainPairView):
    """
    POST /api/mobile/auth/login/
    Returns access + refresh tokens with mobile claims embedded.
    Only cashier and attendant roles are accepted.
    """
    serializer_class = MobileTokenObtainPairSerializer
    permission_classes = [AllowAny]
    throttle_classes = [MobileLoginThrottle]


class MobileTokenRefreshView(TokenRefreshView):
    """
    POST /api/mobile/auth/refresh/
    Re-exported under the mobile namespace. Standard SimpleJWT refresh.
    """
    throttle_classes = [UserRateThrottle]
