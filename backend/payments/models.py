"""
Payments models.

PaymentConfig — tenant-level singleton; selects active provider per channel
                and stores credentials for MTN MoMo, Airtel Money, Pesapal.
PaymentTransaction — one row per initiated payment. Tracks the full lifecycle
                from 'pending' → 'processing' → 'success' / 'failed' /
                'cancelled' / 'expired', plus callback/webhook audit trail.
"""
from django.db import models
from django.utils.timezone import now as timezone_now

from config.validators import validate_provider_url


class PaymentConfig(models.Model):
    """
    Tenant-level payments configuration singleton (one row per tenant schema).

    A tenant may enable multiple providers simultaneously — e.g. MTN for MTN
    numbers, Airtel for Airtel numbers, and Pesapal as a card-payment fallback.
    The "default" provider is used when no specific provider is requested.
    """
    PROVIDER_CHOICES = (
        ('mock', 'Mock (development / testing)'),
        ('mtn', 'MTN Mobile Money'),
        ('airtel', 'Airtel Money'),
        ('pesapal', 'Pesapal (cards + aggregated mobile money)'),
        # ('flutterwave', 'Flutterwave'),  # PINNED — not currently onboarding SMEs
    )

    is_enabled = models.BooleanField(
        default=False,
        help_text='Master switch. When off, all payment initiations are rejected.',
    )
    default_provider = models.CharField(
        max_length=16, choices=PROVIDER_CHOICES, default='mock',
        help_text='Provider used when caller does not specify one explicitly.',
    )
    default_currency = models.CharField(max_length=3, default='UGX')

    # --- MTN MoMo Collections API credentials ---
    mtn_enabled = models.BooleanField(default=False)
    mtn_subscription_key = models.CharField(max_length=255, blank=True)
    mtn_api_user = models.CharField(max_length=255, blank=True)
    mtn_api_key = models.CharField(max_length=255, blank=True)
    mtn_base_url = models.URLField(
        blank=True,
        default='https://sandbox.momodeveloper.mtn.com',
        validators=[validate_provider_url],
    )
    mtn_target_environment = models.CharField(
        max_length=32, blank=True, default='sandbox',
        help_text='"sandbox" for testing, "mtnuganda" for production.',
    )
    mtn_callback_url = models.URLField(blank=True)

    # --- MTN MoMo Disbursements API credentials (if different from collections) ---
    mtn_disbursement_enabled = models.BooleanField(default=False)
    mtn_disbursement_subscription_key = models.CharField(max_length=255, blank=True)
    mtn_disbursement_api_user = models.CharField(max_length=255, blank=True)
    mtn_disbursement_api_key = models.CharField(max_length=255, blank=True)

    # --- Airtel Money API credentials ---
    airtel_enabled = models.BooleanField(default=False)
    airtel_client_id = models.CharField(max_length=255, blank=True)
    airtel_client_secret = models.CharField(max_length=255, blank=True)
    airtel_base_url = models.URLField(
        blank=True,
        default='https://openapiuat.airtel.africa',
        validators=[validate_provider_url],
    )
    airtel_country = models.CharField(max_length=8, blank=True, default='UG')
    airtel_currency = models.CharField(max_length=3, blank=True, default='UGX')
    airtel_callback_url = models.URLField(blank=True)

    # --- Airtel Money Disbursements credentials (if different) ---
    airtel_disbursement_enabled = models.BooleanField(default=False)
    airtel_disbursement_client_id = models.CharField(max_length=255, blank=True)
    airtel_disbursement_client_secret = models.CharField(max_length=255, blank=True)

    # --- Pesapal API v3 credentials (cards + mobile money aggregator) ---
    pesapal_enabled = models.BooleanField(default=False)
    pesapal_consumer_key = models.CharField(max_length=255, blank=True)
    pesapal_consumer_secret = models.CharField(max_length=255, blank=True)
    pesapal_base_url = models.URLField(
        blank=True,
        default='https://cybqa.pesapal.com/pesapalv3',
        validators=[validate_provider_url],
    )
    pesapal_ipn_id = models.CharField(
        max_length=128, blank=True,
        help_text='Registered IPN (Instant Payment Notification) ID from Pesapal.',
    )
    pesapal_callback_url = models.URLField(blank=True)

    created_at = models.DateTimeField(default=timezone_now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Payment Configuration'
        verbose_name_plural = 'Payment Configuration'

    def __str__(self):
        state = 'ENABLED' if self.is_enabled else 'DISABLED'
        return f'Payments [default={self.default_provider}] {state}'

    def save(self, *args, **kwargs):
        # Singleton per tenant schema
        self.pk = 1
        super().save(*args, **kwargs)


class PaymentTransaction(models.Model):
    """
    One row per initiated payment attempt. Each Sale may have multiple
    transactions if the customer retries after a failure.
    """
    STATUS_CHOICES = (
        ('pending', 'Pending — not yet sent to provider'),
        ('processing', 'Processing — awaiting customer / provider'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled by customer'),
        ('expired', 'Expired (timed out)'),
    )

    TYPE_CHOICES = (
        ('collection', 'Collection (customer pays us)'),
        ('disbursement', 'Disbursement (we pay customer/staff/supplier)'),
    )

    METHOD_CHOICES = (
        ('mobile_money', 'Mobile Money'),
        ('card', 'Card'),
        ('bank', 'Bank'),
    )

    PROVIDER_CHOICES = PaymentConfig.PROVIDER_CHOICES

    # Optional link back to a Sale (mobile money may also be used for
    # standalone collections like fuel deposits, so the FK is nullable).
    sale = models.ForeignKey(
        'sales.Sale', on_delete=models.PROTECT,
        null=True, blank=True, related_name='payment_transactions',
    )

    transaction_type = models.CharField(
        max_length=16, choices=TYPE_CHOICES, default='collection', db_index=True,
    )
    provider = models.CharField(max_length=16, choices=PROVIDER_CHOICES)
    method = models.CharField(max_length=16, choices=METHOD_CHOICES)
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default='pending', db_index=True,
    )

    # Amount + currency (immutable once set)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default='UGX')

    # Customer-side identifiers
    phone_number = models.CharField(
        max_length=20, blank=True,
        help_text='MSISDN in international format, e.g. 256772123456 (mobile money only).',
    )
    customer_email = models.CharField(max_length=255, blank=True)
    customer_name = models.CharField(max_length=255, blank=True)

    # Our internal reference (sent to provider as merchantTransactionId)
    reference = models.CharField(max_length=64, unique=True, db_index=True)
    description = models.CharField(max_length=255, blank=True)

    # Provider-side identifiers (populated after initiation)
    provider_transaction_id = models.CharField(
        max_length=128, blank=True, db_index=True,
        help_text="Provider's tracking id (MTN financialTransactionId, Pesapal orderTrackingId, etc.).",
    )
    provider_status_code = models.CharField(max_length=64, blank=True)
    provider_status_message = models.TextField(blank=True)

    # Audit / debugging payloads
    request_payload = models.JSONField(null=True, blank=True)
    response_payload = models.JSONField(null=True, blank=True)
    callback_payload = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    initiated_by = models.IntegerField(
        null=True, blank=True,
        help_text='users.User id of the cashier who initiated this payment.',
    )

    initiated_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone_now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['provider', 'status']),
        ]

    def __str__(self):
        return f'{self.provider}/{self.method} {self.amount} {self.currency} [{self.status}]'

    @property
    def is_terminal(self):
        return self.status in ('success', 'failed', 'cancelled', 'expired')
