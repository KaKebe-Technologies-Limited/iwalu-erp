from django.db import models
from django.utils.timezone import now as timezone_now


class EfrisConfig(models.Model):
    """
    Tenant-level EFRIS configuration singleton. One row per tenant schema.
    Controls which fiscalization provider is used and stores the tenant's
    URA TIN plus provider-specific credentials.
    """
    PROVIDER_CHOICES = (
        ('mock', 'Mock (development / testing)'),
        ('weaf', 'Weaf Company Uganda (production)'),
        ('direct', 'Direct URA (future)'),
    )

    # Tenant tax identity
    tin = models.CharField(
        max_length=20, blank=True,
        help_text='Uganda Revenue Authority Tax Identification Number',
    )
    legal_name = models.CharField(
        max_length=255, blank=True,
        help_text='Name as registered with URA (may differ from business_name)',
    )
    trade_name = models.CharField(max_length=255, blank=True)

    # Provider selection
    provider = models.CharField(
        max_length=10, choices=PROVIDER_CHOICES, default='mock',
    )
    is_enabled = models.BooleanField(
        default=False,
        help_text='Master switch. When off, sales skip fiscalization entirely.',
    )

    # Weaf credentials (encrypted at-rest recommended for production)
    weaf_api_key = models.CharField(max_length=255, blank=True)
    weaf_base_url = models.URLField(blank=True, default='')

    # Defaults applied to every invoice
    default_currency = models.CharField(max_length=3, default='UGX')
    default_tax_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=18.00,
        help_text='Default VAT rate in percent',
    )

    created_at = models.DateTimeField(default=timezone_now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'EFRIS Configuration'
        verbose_name_plural = 'EFRIS Configuration'

    def __str__(self):
        state = 'ENABLED' if self.is_enabled else 'DISABLED'
        return f'EFRIS [{self.provider}] TIN={self.tin or "—"} {state}'

    def save(self, *args, **kwargs):
        # Singleton per tenant schema
        self.pk = 1
        super().save(*args, **kwargs)


class FiscalInvoice(models.Model):
    """
    One row per Sale. Records the submission status to EFRIS and stores the
    fiscal data (FDN, QR, verification code) returned by URA or the provider.
    """
    STATUS_CHOICES = (
        ('pending', 'Pending submission'),
        ('submitted', 'Submitted, awaiting response'),
        ('accepted', 'Accepted by EFRIS'),
        ('rejected', 'Rejected by EFRIS'),
        ('failed', 'Submission failed (retryable)'),
        ('skipped', 'Skipped (fiscalization disabled)'),
    )

    sale = models.OneToOneField(
        'sales.Sale', on_delete=models.PROTECT,
        related_name='fiscal_invoice',
    )
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default='pending', db_index=True,
    )
    provider = models.CharField(max_length=10)

    # EFRIS response fields (populated on acceptance)
    fdn = models.CharField(
        max_length=64, blank=True, db_index=True,
        help_text='Fiscal Document Number assigned by URA',
    )
    invoice_id = models.CharField(
        max_length=64, blank=True,
        help_text="Provider's invoice reference",
    )
    verification_code = models.CharField(
        max_length=64, blank=True,
        help_text='Anti-fake code to print on the receipt',
    )
    qr_code = models.TextField(
        blank=True,
        help_text='QR code data (URL or base64) to print on the receipt',
    )

    # Audit / debugging
    request_payload = models.JSONField(null=True, blank=True)
    response_payload = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)

    submitted_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone_now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f'Fiscal[{self.status}] {self.sale.receipt_number} → {self.fdn or "—"}'

    @property
    def is_fiscalized(self):
        return self.status == 'accepted' and bool(self.fdn)
