from django.db import models


class Account(models.Model):
    """Chart of Accounts entry with optional parent for tree structure."""

    class AccountType(models.TextChoices):
        ASSET = 'asset', 'Asset'
        LIABILITY = 'liability', 'Liability'
        EQUITY = 'equity', 'Equity'
        REVENUE = 'revenue', 'Revenue'
        EXPENSE = 'expense', 'Expense'

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    account_type = models.CharField(max_length=10, choices=AccountType.choices)
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='children',
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False)
    outlet = models.ForeignKey(
        'outlets.Outlet', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='accounts',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class FiscalPeriod(models.Model):
    """Accounting period for closing and reporting."""
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    is_closed = models.BooleanField(default=False)
    closed_by = models.IntegerField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return self.name


class JournalEntry(models.Model):
    """Double-entry accounting transaction header."""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        POSTED = 'posted', 'Posted'
        VOIDED = 'voided', 'Voided'

    class Source(models.TextChoices):
        MANUAL = 'manual', 'Manual'
        SALE = 'sale', 'Sale'
        VOID_SALE = 'void_sale', 'Void Sale'
        PURCHASE = 'purchase', 'Purchase'
        PAYROLL = 'payroll', 'Payroll'
        TRANSFER = 'transfer', 'Transfer'

    entry_number = models.CharField(max_length=50, unique=True)
    date = models.DateField()
    fiscal_period = models.ForeignKey(
        FiscalPeriod, on_delete=models.PROTECT, related_name='entries',
    )
    description = models.TextField()
    source = models.CharField(
        max_length=15, choices=Source.choices, default=Source.MANUAL,
    )
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.IntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT,
    )
    created_by = models.IntegerField()
    posted_by = models.IntegerField(null=True, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.IntegerField(null=True, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name_plural = 'journal entries'

    def __str__(self):
        return f"{self.entry_number} - {self.description[:50]}"


class JournalEntryLine(models.Model):
    """Individual debit or credit line within a journal entry."""
    journal_entry = models.ForeignKey(
        JournalEntry, on_delete=models.CASCADE, related_name='lines',
    )
    account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name='journal_lines',
    )
    description = models.CharField(max_length=300, blank=True)
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    outlet = models.ForeignKey(
        'outlets.Outlet', on_delete=models.SET_NULL,
        null=True, blank=True,
    )

    class Meta:
        ordering = ['id']

    def __str__(self):
        if self.debit > 0:
            return f"DR {self.account.code} {self.debit}"
        return f"CR {self.account.code} {self.credit}"
