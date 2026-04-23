"""
Tenant self-service registration and email verification.

Security posture:
  - Registration disabled by default (TENANT_SELF_REGISTRATION_ENABLED=True to enable).
    While disabled returns 503 — removes the abuse vector entirely during private beta.
  - Per-IP rate-limited (AnonRateThrottle 'tenant-registration' scope).
  - On success returns 201 with pending status but NO JWT tokens. The admin user
    is is_active=False until the email verification link is clicked.
  - Verification token expires in 24 hours and is single-use.
  - Raw exceptions are never surfaced to anonymous callers (leaks Postgres internals).
"""
import logging
from datetime import timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django_tenants.utils import schema_context, get_public_schema_name
from rest_framework import status
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import User
from .models import Client, Domain, TenantEmailVerification
from .serializers import TenantRegistrationSerializer

logger = logging.getLogger(__name__)

_DEFAULT_FROM = 'Nexus ERP <noreply@nexuserp.com>'
_VERIFICATION_EXPIRY_HOURS = 24


class TenantRegistrationThrottle(AnonRateThrottle):
    scope = 'tenant-registration'


def _scheme_for(request) -> str:
    if not settings.DEBUG:
        return 'https'
    return 'https' if request.is_secure() else 'http'


def _send_verification_email(admin_email, token, tenant_schema, scheme, base_domain):
    """Send the email-verification link to the new admin."""
    verify_url = f"{scheme}://{base_domain}/api/tenants/verify-email/?token={token}"
    send_mail(
        subject='Verify your Nexus ERP account',
        message=(
            f"Welcome to Nexus ERP!\n\n"
            f"Your business subdomain will be: {tenant_schema}.{base_domain}\n\n"
            f"Click the link below to verify your email and activate your account "
            f"(expires in {_VERIFICATION_EXPIRY_HOURS} hours):\n\n"
            f"{verify_url}\n\n"
            f"If you did not create a Nexus ERP account, you can ignore this email."
        ),
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', _DEFAULT_FROM),
        recipient_list=[admin_email],
        fail_silently=False,
    )


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([TenantRegistrationThrottle])
def register_tenant(request):
    """
    Public self-service tenant registration.

    Creates a Client + Domain + first admin user atomically. The admin user is
    is_active=False until the email verification link is clicked.
    """
    if not getattr(settings, 'TENANT_SELF_REGISTRATION_ENABLED', False):
        return Response(
            {
                'error': 'Self-service registration is currently disabled.',
                'detail': 'Contact sales@kakebe.com to provision a new tenant.',
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    serializer = TenantRegistrationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    base_domain = getattr(settings, 'TENANT_BASE_DOMAIN', 'localhost')
    full_domain = f"{data['schema_name']}.{base_domain}"
    scheme = _scheme_for(request)

    try:
        with schema_context(get_public_schema_name()):
            with transaction.atomic():
                client = Client.objects.create(
                    schema_name=data['schema_name'],
                    name=data['business_name'],
                )
                Domain.objects.create(
                    domain=full_domain,
                    tenant=client,
                    is_primary=True,
                )
                admin = User.objects.create(
                    email=data['admin_email'],
                    username=data['admin_username'],
                    first_name=data['admin_first_name'],
                    last_name=data['admin_last_name'],
                    phone_number=data.get('admin_phone', ''),
                    role='admin',
                    is_active=False,
                    is_staff=False,
                    is_superuser=False,
                )
                admin.set_password(data['admin_password'])
                admin.save()

                verification = TenantEmailVerification.objects.create(
                    tenant=client,
                    email=data['admin_email'],
                    expires_at=timezone.now() + timedelta(hours=_VERIFICATION_EXPIRY_HOURS),
                )
    except Exception:
        logger.exception('Tenant registration failed for schema %s', data['schema_name'])
        return Response(
            {'error': 'Registration could not be completed. Please try again later.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    try:
        _send_verification_email(
            data['admin_email'], verification.token,
            data['schema_name'], scheme, base_domain,
        )
    except Exception:
        logger.exception(
            'Verification email failed for %s — tenant created, email not sent',
            data['admin_email'],
        )

    return Response(
        {
            'tenant': {
                'id': client.pk,
                'schema_name': client.schema_name,
                'name': client.name,
                'created_on': client.created_on,
            },
            'domain': full_domain,
            'admin_user': {
                'id': admin.pk,
                'email': admin.email,
                'username': admin.username,
                'role': admin.role,
                'is_active': admin.is_active,
            },
            'message': (
                f'Registration received. A verification email has been sent to '
                f'{data["admin_email"]}. Click the link to activate your account.'
            ),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def verify_tenant_email(request):
    """
    Consume an email-verification token, activate the admin user, and return JWT tokens.

    GET /api/tenants/verify-email/?token=<uuid>

    The frontend should store the tokens and redirect_url then navigate to
    the tenant's subdomain dashboard.
    """
    token_str = request.query_params.get('token', '')
    if not token_str:
        return Response({'error': 'Missing token.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        verification = TenantEmailVerification.objects.select_related('tenant').get(token=token_str)
    except (TenantEmailVerification.DoesNotExist, Exception):
        return Response(
            {'error': 'Invalid or expired verification link.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if verification.is_used:
        return Response(
            {'error': 'This verification link has already been used.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if verification.is_expired:
        return Response(
            {'error': 'This verification link has expired. Please register again.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        with schema_context(get_public_schema_name()):
            with transaction.atomic():
                admin = User.objects.get(email=verification.email, is_active=False)
                admin.is_active = True
                admin.save(update_fields=['is_active'])

                verification.used_at = timezone.now()
                verification.save(update_fields=['used_at'])
    except User.DoesNotExist:
        return Response(
            {'error': 'Account not found or already active.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception:
        logger.exception('Email verification failed for token %s', token_str)
        return Response(
            {'error': 'Verification could not be completed. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    refresh = RefreshToken.for_user(admin)
    base_domain = getattr(settings, 'TENANT_BASE_DOMAIN', 'localhost')
    scheme = _scheme_for(request)
    redirect_url = f"{scheme}://{verification.tenant.schema_name}.{base_domain}/dashboard"

    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'redirect_url': redirect_url,
        'tenant': {
            'schema_name': verification.tenant.schema_name,
            'name': verification.tenant.name,
        },
        'message': 'Email verified. Your account is now active.',
    })
