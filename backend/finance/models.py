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


class CashRequisition(models.Model):
    """
    Employee cash request (advance, imprests, operational petty cash).
    Requires manager approval, optionally accountant approval for amounts > threshold.
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending Approval'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        PAID = 'paid', 'Paid'
        SETTLED = 'settled', 'Settled (employee returned balance)'

    class RequisitionType(models.TextChoices):
        PETTY_CASH = 'petty_cash', 'Petty Cash'
        EMPLOYEE_ADVANCE = 'employee_advance', 'Employee Advance'
        OPERATIONAL = 'operational', 'Operational Expense'

    requisition_number = models.CharField(
        max_length=50, unique=True,
        help_text='Auto-generated: REQ-YYYY-##### '
    )
    requisition_type = models.CharField(max_length=30, choices=RequisitionType.choices)
    
    requested_by_id = models.IntegerField(help_text='Employee ID requesting cash')
    requested_at = models.DateTimeField(auto_now_add=True)
    
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default='UGX')
    
    purpose = models.TextField(help_text='Why cash is needed')
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    
    approval_request = models.ForeignKey(
        'approvals.ApprovalRequest', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='cash_requisitions'
    )

    approved_by_id = models.IntegerField(
        null=True, blank=True,
        help_text='Final approver (manager or accountant)'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    paid_by_id = models.IntegerField(null=True, blank=True, help_text='Cashier who paid out')
    paid_at = models.DateTimeField(null=True, blank=True)
    
    settled_amount = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        help_text='Amount returned (if not fully expended)'
    )
    settled_at = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['status', 'requested_by_id']),
        ]

    def __str__(self):
        return f"{self.requisition_number} - {self.amount} {self.currency} ({self.status})"
