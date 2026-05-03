from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.timezone import now as timezone_now
from decimal import Decimal


class SystemConfig(models.Model):
    """
    Tenant-level singleton for system-wide configuration.
    Only one row per tenant schema.
    """
    # Variance & threshold settings
    variance_tolerance_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.50,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text='Acceptable fuel variance percentage (0-10%)',
    )
    low_stock_threshold_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=20.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Low stock alert threshold as % of reorder level',
    )
    low_fuel_threshold_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=25.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Low fuel alert threshold as % of tank capacity',
    )

    # Business details
    business_name = models.CharField(max_length=255, blank=True)
    tax_id = models.CharField(max_length=50, blank=True)
    currency_code = models.CharField(max_length=3, default='UGX')
    timezone = models.CharField(max_length=50, default='Africa/Kampala')
    date_format = models.CharField(max_length=20, default='YYYY-MM-DD')

    # Receipt customisation
    receipt_header = models.TextField(blank=True)
    receipt_footer = models.TextField(blank=True)

    # Notification defaults
    enable_email_notifications = models.BooleanField(default=False)
    enable_sms_notifications = models.BooleanField(default=False)
    
    # Project approval
    project_approval_threshold = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0'),
        help_text='Budget threshold for project approval'
    )

    created_at = models.DateTimeField(default=timezone_now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'System Configuration'
        verbose_name_plural = 'System Configuration'

    def __str__(self):
        return f"System Config (updated {self.updated_at})"

    def save(self, *args, **kwargs):
        # Enforce singleton per tenant schema
        self.pk = 1
        super().save(*args, **kwargs)


class ApprovalThreshold(models.Model):
    TRANSACTION_TYPE_CHOICES = (
        ('purchase_order', 'Purchase Order'),
        ('stock_transfer', 'Stock Transfer'),
        ('expense', 'Expense'),
        ('journal_entry', 'Journal Entry'),
        ('fuel_delivery', 'Fuel Delivery'),
    )
    ROLE_CHOICES = (
        ('manager', 'Manager'),
        ('admin', 'Admin'),
    )

    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    min_amount = models.DecimalField(max_digits=15, decimal_places=2)
    max_amount = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        help_text='Leave blank for unlimited upper bound',
    )
    requires_role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['transaction_type', 'min_amount']
        indexes = [
            models.Index(fields=['transaction_type', 'is_active']),
        ]

    def __str__(self):
        upper = f' - {self.max_amount}' if self.max_amount else '+'
        return f"{self.transaction_type}: {self.min_amount}{upper} -> {self.requires_role}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.max_amount is not None and self.max_amount <= self.min_amount:
            raise ValidationError({
                'max_amount': 'Max amount must be greater than min amount.',
            })


class AuditSetting(models.Model):
    LOG_TYPE_CHOICES = (
        ('login', 'Login Events'),
        ('data_change', 'Data Changes'),
        ('deletion', 'Deletions'),
        ('permission_change', 'Permission Changes'),
        ('export', 'Data Exports'),
    )

    log_type = models.CharField(max_length=20, choices=LOG_TYPE_CHOICES, unique=True)
    is_enabled = models.BooleanField(default=True)
    retention_days = models.PositiveIntegerField(
        default=90,
        validators=[MinValueValidator(7), MaxValueValidator(3650)],
        help_text='Number of days to retain audit logs (7-3650)',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['log_type']

    def __str__(self):
        status = 'ON' if self.is_enabled else 'OFF'
        return f"Audit: {self.log_type} = {status} ({self.retention_days} days)"
