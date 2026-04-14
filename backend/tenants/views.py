import logging
from django.conf import settings
from django.db import transaction
from django_tenants.utils import schema_context, get_public_schema_name
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import User
from .models import Client, Domain
from .serializers import TenantRegistrationSerializer

logger = logging.getLogger(__name__)


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def register_tenant(request):
    """
    Public self-service tenant registration.

    Atomically creates:
      1. A Client (tenant) with its own PostgreSQL schema
      2. A Domain mapping {schema_name}.{base_domain} to the tenant
      3. The first admin user (role=admin) in the shared user table

    Returns the tenant details plus JWT tokens for the admin user so the
    client can immediately log in to the new tenant.
    """
    serializer = TenantRegistrationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    base_domain = getattr(settings, 'TENANT_BASE_DOMAIN', 'localhost')
    full_domain = f"{data['schema_name']}.{base_domain}"

    try:
        # Tenant + Domain + User creation must run against the public schema,
        # regardless of which subdomain the request came in on. schema_context
        # switches the connection to 'public' for the duration of the block.
        with schema_context(get_public_schema_name()):
            with transaction.atomic():
                # 1. Create the tenant (triggers schema creation + migrations)
                client = Client.objects.create(
                    schema_name=data['schema_name'],
                    name=data['business_name'],
                )

                # 2. Create the primary domain for the tenant
                Domain.objects.create(
                    domain=full_domain,
                    tenant=client,
                    is_primary=True,
                )

                # 3. Create the first admin user (in the public schema,
                #    since users is in SHARED_APPS)
                admin = User.objects.create(
                    email=data['admin_email'],
                    username=data['admin_username'],
                    first_name=data['admin_first_name'],
                    last_name=data['admin_last_name'],
                    phone_number=data.get('admin_phone', ''),
                    role='admin',
                    is_active=True,
                )
                admin.set_password(data['admin_password'])
                admin.save()
    except Exception as exc:
        logger.exception('Tenant registration failed for schema %s', data['schema_name'])
        return Response(
            {'error': 'Tenant registration failed.', 'detail': str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # 4. Issue JWT tokens so the client can immediately authenticate
    refresh = RefreshToken.for_user(admin)

    scheme = 'https' if request.is_secure() else 'http'
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
                'first_name': admin.first_name,
                'last_name': admin.last_name,
                'role': admin.role,
            },
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        },
        status=status.HTTP_201_CREATED,
    )
