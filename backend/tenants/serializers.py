import re
from django.conf import settings
from rest_framework import serializers
from users.models import User
from .models import (
    Client, Domain, SubscriptionPlan, TenantSubscription, SubscriptionInvoice
)


# Reserved subdomain names that cannot be used as tenants
RESERVED_SCHEMA_NAMES = frozenset({
    'public', 'www', 'api', 'admin', 'app', 'auth', 'mail', 'ftp',
    'blog', 'help', 'support', 'docs', 'status', 'dev', 'staging',
    'test', 'tests', 'postgres', 'information_schema', 'pg_catalog',
})

# Subdomain-safe: lowercase letters/digits/hyphen, must start with a letter.
# Underscores are intentionally disallowed because RFC1035 forbids them in
# DNS labels (cookies, TLS hostnames, and many CDNs reject them).
SCHEMA_NAME_PATTERN = re.compile(r'^[a-z][a-z0-9-]{2,29}$')


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

    # Subscription info
    plan_id = serializers.IntegerField(help_text='ID of the chosen subscription plan')
    billing_cycle = serializers.ChoiceField(
        choices=TenantSubscription.BillingCycle.choices,
        default=TenantSubscription.BillingCycle.MONTHLY
    )

    def validate_plan_id(self, value):
        if not SubscriptionPlan.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError('Invalid or inactive plan selected.')
        return value

    def validate_schema_name(self, value):
        value = value.lower().strip()

        if not SCHEMA_NAME_PATTERN.match(value):
            raise serializers.ValidationError(
                'Identifier must be 3-30 characters, lowercase letters, '
                'digits, or hyphens, and must start with a letter.'
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


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    monthly_equivalent = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'slug', 'name', 'price_monthly', 'price_annual',
            'max_users', 'max_outlets', 'features', 'description',
            'is_active', 'display_order', 'monthly_equivalent'
        ]


class TenantSubscriptionSerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanSerializer(read_only=True)
    tenant = serializers.SlugRelatedField(slug_field='schema_name', read_only=True)
    trial_days_remaining = serializers.SerializerMethodField()
    is_trial = serializers.SerializerMethodField()

    class Meta:
        model = TenantSubscription
        fields = [
            'id', 'tenant', 'plan', 'billing_cycle', 'status',
            'is_trial', 'trial_days_remaining', 'current_period_start',
            'current_period_end', 'next_billing_date', 'failed_payment_count',
            'suspended_at', 'suspension_reason'
        ]

    def get_is_trial(self, obj):
        return obj.status == TenantSubscription.Status.TRIAL

    def get_trial_days_remaining(self, obj):
        if not obj.trial_started_at:
            return 0
        from django.utils import timezone
        from datetime import timedelta
        expiry = obj.trial_started_at + timedelta(days=obj.trial_days)
        remaining = (expiry - timezone.now()).days
        return max(0, remaining)


class SubscriptionInvoiceSerializer(serializers.ModelSerializer):
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = SubscriptionInvoice
        fields = [
            'id', 'invoice_number', 'period_start', 'period_end',
            'amount', 'status', 'issued_at', 'due_date', 'paid_at',
            'is_overdue', 'notes', 'line_items'
        ]


class ChangePlanSerializer(serializers.Serializer):
    plan_id = serializers.IntegerField()
    billing_cycle = serializers.ChoiceField(choices=TenantSubscription.BillingCycle.choices)

    def validate_plan_id(self, value):
        if not SubscriptionPlan.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Plan not found or inactive.")
        return value


class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()
