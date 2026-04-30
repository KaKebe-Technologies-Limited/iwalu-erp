import logging
from django.db import connection
from django.core.cache import cache
from rest_framework.exceptions import ValidationError

from .models import SystemConfig, ApprovalThreshold

logger = logging.getLogger(__name__)

SYSTEM_CONFIG_CACHE_TTL = 300  # 5 minutes

# Fields that can be updated via the API
ALLOWED_CONFIG_FIELDS = frozenset({
    'variance_tolerance_pct', 'low_stock_threshold_pct', 'low_fuel_threshold_pct',
    'business_name', 'tax_id', 'currency_code', 'timezone', 'date_format',
    'receipt_header', 'receipt_footer',
    'enable_email_notifications', 'enable_sms_notifications',
})


def _cache_key():
    return f'system_config:{connection.schema_name}'


def get_system_config():
    """
    Return the tenant's SystemConfig singleton, creating defaults if needed.
    Uses tenant-scoped cache to avoid DB hits on every request.
    """
    key = _cache_key()
    config = cache.get(key)
    if config is None:
        config, _ = SystemConfig.objects.get_or_create(pk=1)
        cache.set(key, config, SYSTEM_CONFIG_CACHE_TTL)
    return config


def update_system_config(validated_data):
    """Update system config from serializer-validated data and invalidate cache."""
    config = get_system_config()
    for field, value in validated_data.items():
        if field in ALLOWED_CONFIG_FIELDS:
            setattr(config, field, value)
    config.full_clean()
    config.save()
    cache.delete(_cache_key())
    return config


def get_required_approval_role(transaction_type, amount):
    """
    Determine if a transaction requires approval and which role.
    Returns the required role string, or None if no approval needed.
    """
    thresholds = (
        ApprovalThreshold.objects
        .filter(
            transaction_type=transaction_type,
            is_active=True,
            min_amount__lte=amount,
        )
        .order_by('-min_amount')
    )

    for threshold in thresholds:
        if threshold.max_amount is None or amount <= threshold.max_amount:
            return threshold.requires_role

    return None


def check_approval(transaction_type, amount, user_role):
    """
    Check whether a user's role satisfies the approval requirement.
    Returns (approved: bool, required_role: str|None).
    """
    required_role = get_required_approval_role(transaction_type, amount)
    if required_role is None:
        return True, None

    role_hierarchy = {'admin': 2, 'manager': 1}
    user_level = role_hierarchy.get(user_role, 0)
    required_level = role_hierarchy.get(required_role, 0)

    return user_level >= required_level, required_role
