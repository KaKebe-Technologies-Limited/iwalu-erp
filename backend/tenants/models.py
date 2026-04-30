import uuid
from datetime import timedelta, date
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from django_tenants.models import TenantMixin, DomainMixin


class Client(TenantMixin):
    name = models.CharField(max_length=100)
    created_on = models.DateField(auto_now_add=True)

    auto_create_schema = True


class Domain(DomainMixin):
    pass


class TenantEmailVerification(models.Model):
    """
    One-time token issued at tenant registration.
    Admin user stays is_active=False until this token is consumed.
    """
    tenant = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='email_verifications')
    email = models.EmailField()
    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Verification for {self.email} ({self.tenant.schema_name})"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_used(self):
        return self.used_at is not None


class SubscriptionPlan(models.Model):
    """
    SaaS pricing tiers. Admin-managed only.
    One plan per month/year cycle; businesses choose which to use when registering.
    """
    class BillingCycle(models.TextChoices):
        MONTHLY = 'monthly', 'Monthly'
        ANNUAL = 'annual', 'Annual'

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, help_text='e.g., "starter", "professional", "enterprise"')
    
    # Pricing
    price_monthly = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        help_text='Monthly subscription price (UGX)'
    )
    price_annual = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        help_text='Annual subscription price (UGX). Can be less than 12x monthly.'
    )
    
    # Limits
    max_users = models.PositiveIntegerField(help_text='Max concurrent user seats')
    max_outlets = models.PositiveIntegerField(help_text='Max physical outlets/branches')
    
    # Features (JSON — list of feature keys like 'fuel_management', 'hr_module', 'project_management')
    features = models.JSONField(
        default=list, blank=True,
        help_text='List of enabled feature slugs: ["pos", "inventory", "fuel", "hr", "accounting", "project_management", "asset_management"]'
    )
    
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, help_text='Inactive plans cannot be selected at registration')
    display_order = models.PositiveIntegerField(default=0, help_text='Sort order on pricing page')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'price_monthly']

    def __str__(self):
        return f"{self.name} (UGX {self.price_monthly}/mo, {self.max_users} users)"

    def monthly_cost(self):
        return self.price_monthly

    def annual_cost(self):
        return self.price_annual

    def monthly_equivalent(self):
        """For comparison: annual price / 12."""
        return self.price_annual / Decimal('12')


class TenantSubscription(models.Model):
    """
    Active subscription for a tenant. Links tenant to plan + tracks billing state.
    """
    class Status(models.TextChoices):
        TRIAL = 'trial', 'Trial'
        ACTIVE = 'active', 'Active'
        SUSPENDED = 'suspended', 'Suspended (payment overdue)'
        CANCELLED = 'cancelled', 'Cancelled'
        PAST_DUE = 'past_due', 'Past Due'

    class BillingCycle(models.TextChoices):
        MONTHLY = 'monthly', 'Monthly'
        ANNUAL = 'annual', 'Annual'

    tenant = models.OneToOneField(Client, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    billing_cycle = models.CharField(max_length=10, choices=BillingCycle.choices)
    
    # Trial period
    trial_started_at = models.DateTimeField(null=True, blank=True)
    trial_days = models.PositiveIntegerField(default=14, help_text='Default trial period in days')
    
    # Billing state
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TRIAL)
    current_period_start = models.DateTimeField(help_text='Billing period start (current or upcoming)')
    current_period_end = models.DateTimeField(help_text='Billing period end; next invoice due then')
    next_billing_date = models.DateTimeField(help_text='When next payment attempt should occur')
    
    # Suspension tracking
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.CharField(
        max_length=255, blank=True,
        help_text='e.g., "Invoice overdue 30+ days"'
    )
    
    # Finance
    failed_payment_count = models.PositiveIntegerField(default=0)
    last_payment_attempt_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'next_billing_date']),
            models.Index(fields=['tenant', 'status']),
        ]

    def __str__(self):
        return f"{self.tenant.name} → {self.plan.name} ({self.get_billing_cycle_display()})"

    @property
    def is_active(self):
        return self.status in [self.Status.ACTIVE, self.Status.TRIAL]

    @property
    def is_trial_active(self):
        if not self.trial_started_at:
            return False
        return timezone.now() < self.trial_started_at + timedelta(days=self.trial_days)

    def can_upgrade(self):
        """Check if tenant can change plans."""
        return self.status in [self.Status.ACTIVE, self.Status.TRIAL]

    def suspend(self, reason: str):
        """Suspend tenant and log reason."""
        self.status = self.Status.SUSPENDED
        self.suspended_at = timezone.now()
        self.suspension_reason = reason
        self.save(update_fields=['status', 'suspended_at', 'suspension_reason'])

    def reactivate(self):
        """Reactivate suspended tenant."""
        self.status = self.Status.ACTIVE
        self.suspended_at = None
        self.suspension_reason = ''
        self.failed_payment_count = 0
        self.save(update_fields=['status', 'suspended_at', 'suspension_reason', 'failed_payment_count'])


class SubscriptionInvoice(models.Model):
    """
    Monthly/annual billing invoice. One per billing cycle per subscription.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Payment'
        PAID = 'paid', 'Paid'
        OVERDUE = 'overdue', 'Overdue'
        CANCELLED = 'cancelled', 'Cancelled'
        REFUNDED = 'refunded', 'Refunded'

    subscription = models.ForeignKey(
        TenantSubscription, on_delete=models.CASCADE, related_name='invoices'
    )
    invoice_number = models.CharField(
        max_length=50, unique=True,
        help_text='Auto-generated: e.g., INV-2026-00001'
    )
    
    # Billing period
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Financials
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    
    # Dates
    issued_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField(help_text='Payment due date (e.g., 14 days after issued)')
    paid_at = models.DateTimeField(null=True, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    # Line items (for future detailed invoicing)
    line_items = models.JSONField(
        default=list, blank=True,
        help_text='[{"description": "Plan fee", "quantity": 1, "unit_price": 500000, "total": 500000}]'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-period_end', '-created_at']
        indexes = [
            models.Index(fields=['subscription', 'status']),
            models.Index(fields=['due_date', 'status']),
        ]
        unique_together = ('subscription', 'period_start', 'period_end')

    def __str__(self):
        return f"{self.invoice_number} ({self.subscription.tenant.name}) - {self.status}"

    @property
    def is_overdue(self):
        return (
            self.status == self.Status.PENDING and
            date.today() > self.due_date
        )

    def mark_paid(self):
        """Record payment."""
        self.status = self.Status.PAID
        self.paid_at = timezone.now()
        self.save(update_fields=['status', 'paid_at'])
