"""
Tenant self-service registration.

Security posture:
  - Disabled by default. Set TENANT_SELF_REGISTRATION_ENABLED=True in env to
    expose the endpoint. While disabled, returns 503 + a "contact sales"
    message — matches the current go-to-market reality and removes the
    abuse vector entirely.
  - Per-IP rate-limited (DRF AnonRateThrottle 'tenant-registration' scope).
  - On success returns 201 with tenant info but NO JWT tokens. The caller
    must complete email verification (out-of-band, currently manual via
    Kakebe staff) before the admin user is activated and can log in.
  - Errors are not surfaced raw to anonymous callers (would leak Postgres
    internals). Detailed errors go to logs.

When the proper email-verification + async-provisioning flow is built, the
flag flips to True and the body of `register_tenant` shrinks to "create
TenantRegistrationRequest, send verification email."
"""
import logging
from django.conf import settings
from django.db import transaction
from django_tenants.utils import schema_context, get_public_schema_name
from rest_framework import status
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from users.models import User
from .models import Client, Domain
from .serializers import TenantRegistrationSerializer

logger = logging.getLogger(__name__)


class TenantRegistrationThrottle(AnonRateThrottle):
    scope = 'tenant-registration'


def _scheme_for(request) -> str:
    """Force https outside DEBUG, regardless of how the request was framed."""
    if not settings.DEBUG:
        return 'https'
    return 'https' if request.is_secure() else 'http'


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([TenantRegistrationThrottle])
def register_tenant(request):
    """
    Public self-service tenant registration.

    Creates a Client + Domain + first admin user atomically. The created
    admin user is `is_active=False`; activation requires out-of-band email
    verification (currently a manual step performed by Kakebe staff).
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

    try:
        # Tenant + Domain + User creation must run against the public schema,
        # regardless of which subdomain the request came in on.
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
                # First admin is created INACTIVE. Out-of-band email
                # verification (currently manual) flips is_active=True.
                # Explicitly clamp staff/superuser flags — defense in depth
                # against future model defaults shifting.
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
    except Exception:
        logger.exception('Tenant registration failed for schema %s', data['schema_name'])
        # Do NOT echo the raw exception to anonymous callers — it leaks
        # Postgres schema/SQL details.
        return Response(
            {'error': 'Registration could not be completed. Please try again later.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    scheme = _scheme_for(request)
    return Response(
        {
            'tenant': {
                'id': client.pk,
                'schema_name': client.schema_name,
                'name': client.name,
                'created_on': client.created_on,
            },
            'domain': full_domain,
            'login_url': f'{scheme}://{full_domain}/api/auth/login/',
            'admin_user': {
                'id': admin.pk,
                'email': admin.email,
                'username': admin.username,
                'role': admin.role,
                'is_active': admin.is_active,
            },
            'message': (
                'Registration received. Your account is pending verification. '
                'You will receive an email once it is activated.'
            ),
        },
        status=status.HTTP_201_CREATED,
    )
