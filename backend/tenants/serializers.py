import re
from django.conf import settings
from rest_framework import serializers
from users.models import User
from .models import Client, Domain


# Reserved subdomain names that cannot be used as tenants
RESERVED_SCHEMA_NAMES = frozenset({
    'public', 'www', 'api', 'admin', 'app', 'auth', 'mail', 'ftp',
    'blog', 'help', 'support', 'docs', 'status', 'dev', 'staging',
    'test', 'tests', 'postgres', 'information_schema', 'pg_catalog',
})

SCHEMA_NAME_PATTERN = re.compile(r'^[a-z][a-z0-9_]{2,29}$')


class TenantRegistrationSerializer(serializers.Serializer):
    """
    Public self-service tenant registration.
    Creates a Client + Domain + first admin user atomically.
    """
    # Business info
    business_name = serializers.CharField(max_length=100)
    schema_name = serializers.CharField(
        max_length=30,
        help_text='Subdomain identifier (lowercase, 3-30 chars, letters/digits/underscore, '
                  'must start with a letter). This becomes your subdomain.',
    )

    # First admin user
    admin_email = serializers.EmailField()
    admin_username = serializers.CharField(max_length=150)
    admin_password = serializers.CharField(write_only=True, min_length=8)
    admin_first_name = serializers.CharField(max_length=150)
    admin_last_name = serializers.CharField(max_length=150)
    admin_phone = serializers.CharField(
        max_length=20, required=False, allow_blank=True, default='',
    )

    def validate_schema_name(self, value):
        value = value.lower().strip()

        if not SCHEMA_NAME_PATTERN.match(value):
            raise serializers.ValidationError(
                'Schema name must be 3-30 characters, lowercase letters, '
                'digits, or underscores, and must start with a letter.'
            )
        if value in RESERVED_SCHEMA_NAMES:
            raise serializers.ValidationError(
                f'"{value}" is a reserved name and cannot be used.'
            )
        if Client.objects.filter(schema_name=value).exists():
            raise serializers.ValidationError(
                f'A business with the identifier "{value}" already exists.'
            )
        return value

    def validate_admin_email(self, value):
        value = value.lower().strip()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                'A user with this email already exists.'
            )
        return value

    def validate_admin_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(
                'A user with this username already exists.'
            )
        return value

    def validate(self, data):
        # Final uniqueness check for the constructed domain
        base_domain = getattr(settings, 'TENANT_BASE_DOMAIN', 'localhost')
        full_domain = f"{data['schema_name']}.{base_domain}"
        if Domain.objects.filter(domain=full_domain).exists():
            raise serializers.ValidationError({
                'schema_name': f'The domain "{full_domain}" is already registered.',
            })
        return data


class TenantRegistrationResponseSerializer(serializers.Serializer):
    """Response payload after successful tenant registration."""
    tenant = serializers.DictField()
    domain = serializers.CharField()
    admin_user = serializers.DictField()
    access = serializers.CharField()
    refresh = serializers.CharField()
