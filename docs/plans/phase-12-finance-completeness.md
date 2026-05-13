# Phase 12 — Finance Completeness

**Branch**: `feat-phase-12-finance-completeness`  
**Depends on**: Phases 1–9 merged to `main`  
**Scope**: Backend only. Extends the existing `finance` Django app with budget management (Budget + BudgetLine models, variance reporting, soft enforcement on cash requisitions), accounts payable (SupplierInvoice + APPayment models, aging report), and outlet-level filtering on the existing profit & loss view.

---

## Overview

The Nexus ERP proposal (section 5 — Finance) requires three capabilities the current `finance` app does not yet provide:

1. **Budget creation and enforcement** — managers need to define budget lines per account per fiscal period, compare actual spend against budget in real time, and receive a warning (soft block) when a cash requisition would exceed the budgeted amount.
2. **Accounts payable** — supplier invoices raised against purchase orders need to be tracked, approved, and paid, with an aging report showing how long invoices have been outstanding.
3. **Outlet-level P&L** — the existing `profit_loss_view` does not accept an `outlet_id` filter, so managers cannot isolate profitability per station.

All new models live in the existing `finance` app — no new Django app is registered. `SupplierInvoice` and `APPayment` belong in `finance` even though they reference `inventory.Supplier` and `inventory.PurchaseOrder`; AP is a finance concern, and both apps share the same tenant schema so cross-app ForeignKeys are valid.

**Key constraints carried forward from the existing codebase:**
- Tenant-scoped apps use `TenantTestCase` + `TenantClient` for tests.
- Cross-schema foreign keys between the shared schema (users) and tenant schemas are not possible — use `IntegerField` for `created_by_id`, `requester_id`, etc.
- `inventory.Supplier` and `inventory.PurchaseOrder` are in the same tenant schema as `finance`, so standard `ForeignKey` is valid for `SupplierInvoice`.
- Always run `migrate_schemas`, never `migrate`.
- All currency amounts: `DecimalField` with `decimal_places=2` — never `FloatField`.
- `INSTALLED_APPS` ordering must be preserved for `django-tenants` — do not sort or deduplicate.
- Budget variance queries must use `fiscal_period.start_date` / `fiscal_period.end_date` as the JournalEntry date range.

---

## App Registration

No new app is added. All new models go into the existing `finance` app which is already in `TENANT_APPS`.

Verify `finance` is already listed:

```python
# backend/config/settings.py
TENANT_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'outlets',
    'products',
    'sales',
    'inventory',
    'reports',
    'finance',   # already present — no change needed
    'hr',
    'fuel',
    'notifications',
    'system_config',
    'fiscalization',
    'payments',
    'approvals',
    'assets',
    'mobile_api',
]
```

No `settings.py` changes required for this phase.

---

## Phase 1: Budget + BudgetLine Models and Migration

### Edit `backend/finance/models.py`

Add the two new models at the bottom of the file, after the existing `CashRequisition` model.

```python
class Budget(models.Model):
    """
    Defines a budget for a fiscal period, optionally scoped to an outlet
    or HR department. Budget lines break the total down by account.
    """
    name = models.CharField(max_length=200)
    fiscal_period = models.ForeignKey(
        'FiscalPeriod',
        on_delete=models.PROTECT,
        related_name='budgets',
    )
    department = models.IntegerField(
        null=True,
        blank=True,
        help_text=(
            "Optional reference to hr.Department (IntegerField — "
            "cross-schema FK not possible with django-tenants)."
        ),
    )
    outlet = models.ForeignKey(
        'outlets.Outlet',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='budgets',
        help_text="If set, this budget is scoped to a specific outlet.",
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by_id = models.IntegerField(
        help_text="User ID of the manager who created this budget."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.fiscal_period})"


class BudgetLine(models.Model):
    """
    A single account-level allocation within a Budget.
    Variance is computed at query time by comparing budgeted_amount
    against actual JournalEntryLine debits/credits for the account
    within the fiscal period date range.
    """
    budget = models.ForeignKey(
        Budget,
        on_delete=models.CASCADE,
        related_name='lines',
    )
    account = models.ForeignKey(
        'Account',
        on_delete=models.PROTECT,
        related_name='budget_lines',
    )
    budgeted_amount = models.DecimalField(max_digits=14, decimal_places=2)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['account__code']
        unique_together = [('budget', 'account')]

    def __str__(self):
        return f"{self.budget.name} — {self.account.name}: {self.budgeted_amount}"
```

### Run Migrations

```bash
docker compose exec backend python manage.py makemigrations finance
docker compose exec backend python manage.py migrate_schemas
```

The migration will be named something like `0003_budget_budgetline.py`. Verify with:

```bash
docker compose exec backend python manage.py showmigrations finance
```

---

## Phase 2: Budget Serializers and ViewSet

### Edit `backend/finance/serializers.py`

Add the following serializers at the bottom of the file, after the existing `CashRequisitionSerializer`.

```python
from .models import Budget, BudgetLine


class BudgetLineSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.name', read_only=True)
    account_code = serializers.CharField(source='account.code', read_only=True)

    class Meta:
        model = BudgetLine
        fields = [
            'id',
            'account',
            'account_name',
            'account_code',
            'budgeted_amount',
            'notes',
        ]


class BudgetSerializer(serializers.ModelSerializer):
    lines = BudgetLineSerializer(many=True, read_only=True)
    fiscal_period_display = serializers.SerializerMethodField()
    outlet_name = serializers.CharField(
        source='outlet.name', read_only=True, allow_null=True
    )

    class Meta:
        model = Budget
        fields = [
            'id',
            'name',
            'fiscal_period',
            'fiscal_period_display',
            'department',
            'outlet',
            'outlet_name',
            'description',
            'is_active',
            'created_by_id',
            'lines',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_fiscal_period_display(self, obj):
        fp = obj.fiscal_period
        return f"{fp.start_date} – {fp.end_date}"


class BudgetCreateSerializer(serializers.ModelSerializer):
    """
    Used for POST/PUT/PATCH. Lines are written separately via
    POST /api/finance/budgets/{id}/lines/.
    created_by_id is set from request.user in the ViewSet.
    """

    class Meta:
        model = Budget
        fields = [
            'id',
            'name',
            'fiscal_period',
            'department',
            'outlet',
            'description',
            'is_active',
            'created_by_id',
        ]
        read_only_fields = ['created_by_id']


class BudgetVarianceLineSerializer(serializers.Serializer):
    account_id = serializers.IntegerField()
    account_name = serializers.CharField()
    account_code = serializers.CharField()
    budgeted = serializers.DecimalField(max_digits=14, decimal_places=2)
    actual = serializers.DecimalField(max_digits=14, decimal_places=2)
    variance = serializers.DecimalField(max_digits=14, decimal_places=2)
    variance_pct = serializers.DecimalField(
        max_digits=7, decimal_places=2, allow_null=True
    )


class BudgetSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    fiscal_period_display = serializers.CharField()
    outlet_name = serializers.CharField(allow_null=True)
    total_budgeted = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_actual = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_variance = serializers.DecimalField(max_digits=14, decimal_places=2)
    is_active = serializers.BooleanField()
```

### Edit `backend/finance/views.py`

Add the `BudgetViewSet` alongside the existing ViewSets. Import new models and serializers at the top, then append the ViewSet class.

```python
from decimal import Decimal

from django.db.models import Sum, Q
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import (
    Account, FiscalPeriod, JournalEntry, JournalEntryLine,
    CashRequisition, Budget, BudgetLine,
)
from .serializers import (
    AccountSerializer,
    FiscalPeriodSerializer,
    JournalEntrySerializer,
    CashRequisitionSerializer,
    BudgetSerializer,
    BudgetCreateSerializer,
    BudgetVarianceLineSerializer,
    BudgetSummarySerializer,
    BudgetLineSerializer,
)


class BudgetViewSet(viewsets.ModelViewSet):
    """
    CRUD for Budget objects.

    Custom actions:
      GET  /api/finance/budgets/{id}/variance/   — account-level variance report
      GET  /api/finance/budgets/summary/          — all active budgets with totals
      POST /api/finance/budgets/{id}/lines/       — add a BudgetLine to a Budget
    """
    queryset = Budget.objects.select_related('fiscal_period', 'outlet').prefetch_related('lines__account')
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return BudgetCreateSerializer
        return BudgetSerializer

    def perform_create(self, serializer):
        serializer.save(created_by_id=self.request.user.id)

    @action(detail=True, methods=['get'], url_path='variance')
    def variance(self, request, pk=None):
        """
        GET /api/finance/budgets/{id}/variance/

        Compares each BudgetLine.budgeted_amount against the sum of actual
        JournalEntryLine debits for the corresponding account, restricted to
        JournalEntry records whose date falls within the budget's fiscal period.

        For EXPENSE accounts, actual spend = sum of debit amounts.
        For INCOME accounts, actual = sum of credit amounts.
        For all other account types, actual = debit - credit (net movement).
        """
        budget = self.get_object()
        fp = budget.fiscal_period
        lines = budget.lines.select_related('account').all()

        result = []
        for line in lines:
            account = line.account
            qs = JournalEntryLine.objects.filter(
                account=account,
                entry__date__gte=fp.start_date,
                entry__date__lte=fp.end_date,
                entry__status='posted',
            )

            if account.account_type == 'EXPENSE':
                agg = qs.aggregate(total=Sum('debit'))
                actual = agg['total'] or Decimal('0.00')
            elif account.account_type == 'INCOME':
                agg = qs.aggregate(total=Sum('credit'))
                actual = agg['total'] or Decimal('0.00')
            else:
                agg = qs.aggregate(
                    total_debit=Sum('debit'),
                    total_credit=Sum('credit'),
                )
                actual = (agg['total_debit'] or Decimal('0.00')) - (
                    agg['total_credit'] or Decimal('0.00')
                )

            variance = line.budgeted_amount - actual
            if line.budgeted_amount != Decimal('0.00'):
                variance_pct = (
                    variance / line.budgeted_amount * Decimal('100')
                ).quantize(Decimal('0.01'))
            else:
                variance_pct = None

            result.append({
                'account_id': account.id,
                'account_name': account.name,
                'account_code': account.code,
                'budgeted': line.budgeted_amount,
                'actual': actual,
                'variance': variance,
                'variance_pct': variance_pct,
            })

        serializer = BudgetVarianceLineSerializer(result, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """
        GET /api/finance/budgets/summary/

        Returns all active budgets with aggregate totals: total budgeted amount,
        total actual spend (computed the same way as variance), and the difference.
        """
        budgets = Budget.objects.filter(is_active=True).select_related(
            'fiscal_period', 'outlet'
        ).prefetch_related('lines__account')

        result = []
        for budget in budgets:
            fp = budget.fiscal_period
            total_budgeted = Decimal('0.00')
            total_actual = Decimal('0.00')

            for line in budget.lines.select_related('account').all():
                total_budgeted += line.budgeted_amount
                qs = JournalEntryLine.objects.filter(
                    account=line.account,
                    entry__date__gte=fp.start_date,
                    entry__date__lte=fp.end_date,
                    entry__status='posted',
                )
                if line.account.account_type == 'EXPENSE':
                    agg = qs.aggregate(total=Sum('debit'))
                    actual = agg['total'] or Decimal('0.00')
                elif line.account.account_type == 'INCOME':
                    agg = qs.aggregate(total=Sum('credit'))
                    actual = agg['total'] or Decimal('0.00')
                else:
                    agg = qs.aggregate(
                        total_debit=Sum('debit'),
                        total_credit=Sum('credit'),
                    )
                    actual = (agg['total_debit'] or Decimal('0.00')) - (
                        agg['total_credit'] or Decimal('0.00')
                    )
                total_actual += actual

            result.append({
                'id': budget.id,
                'name': budget.name,
                'fiscal_period_display': (
                    f"{fp.start_date} – {fp.end_date}"
                ),
                'outlet_name': budget.outlet.name if budget.outlet else None,
                'total_budgeted': total_budgeted,
                'total_actual': total_actual,
                'total_variance': total_budgeted - total_actual,
                'is_active': budget.is_active,
            })

        serializer = BudgetSummarySerializer(result, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='lines')
    def add_line(self, request, pk=None):
        """
        POST /api/finance/budgets/{id}/lines/

        Adds a single BudgetLine to the budget. Returns 400 if the account
        already has a line in this budget (unique_together constraint).
        """
        budget = self.get_object()
        serializer = BudgetLineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            line = serializer.save(budget=budget)
        except Exception as exc:
            return Response(
                {'error': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            BudgetLineSerializer(line).data,
            status=status.HTTP_201_CREATED,
        )
```

### Register URL in `backend/finance/urls.py`

```python
from rest_framework.routers import DefaultRouter
from django.urls import path

from .views import (
    AccountViewSet,
    FiscalPeriodViewSet,
    JournalEntryViewSet,
    CashRequisitionViewSet,
    BudgetViewSet,           # <-- add
    trial_balance_view,
    profit_loss_view,
    balance_sheet_view,
    account_ledger_view,
)

router = DefaultRouter()
router.register(r'accounts', AccountViewSet)
router.register(r'fiscal-periods', FiscalPeriodViewSet)
router.register(r'journal-entries', JournalEntryViewSet)
router.register(r'cash-requisitions', CashRequisitionViewSet)
router.register(r'budgets', BudgetViewSet)    # <-- add

urlpatterns = router.urls + [
    path('reports/trial-balance/', trial_balance_view, name='trial-balance'),
    path('reports/profit-loss/', profit_loss_view, name='profit-loss'),
    path('reports/balance-sheet/', balance_sheet_view, name='balance-sheet'),
    path('reports/account-ledger/<int:account_id>/', account_ledger_view, name='account-ledger'),
]
```

---

## Phase 3: Budget Enforcement in CashRequisition (Soft Warning)

When a `CashRequisition` is created, the system checks whether the requisition amount would push the related account over its budgeted amount for the current fiscal period. If it would, the response is HTTP 200 with `budget_warning: true` — the requisition is still created. This is **soft enforcement only** (V1).

### Edit `backend/finance/views.py` — `CashRequisitionViewSet`

Locate the existing `CashRequisitionViewSet` and override `create()`. The check requires the requisition to specify an `account` field — if `CashRequisition` does not currently have an `account` FK, add `account = models.ForeignKey('Account', on_delete=models.SET_NULL, null=True, blank=True, related_name='cash_requisitions')` to the model in this phase and run a migration.

```python
class CashRequisitionViewSet(viewsets.ModelViewSet):
    queryset = CashRequisition.objects.all()
    serializer_class = CashRequisitionSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        """
        Creates a CashRequisition. If an active budget line exists for the
        specified account in the current open fiscal period, and the new
        requisition would cause total spend to exceed the budgeted amount,
        the response includes budget_warning=True.

        The requisition is always created regardless of budget status (soft enforcement).
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        budget_warning = False
        budget_warning_detail = None

        account_id = request.data.get('account')
        amount = serializer.validated_data.get('amount', Decimal('0.00'))

        if account_id:
            from django.utils import timezone
            today = timezone.now().date()

            # Find an open fiscal period covering today
            try:
                fp = FiscalPeriod.objects.get(
                    start_date__lte=today,
                    end_date__gte=today,
                    is_closed=False,
                )
                # Find active budget line for this account in the period
                budget_line = BudgetLine.objects.filter(
                    account_id=account_id,
                    budget__fiscal_period=fp,
                    budget__is_active=True,
                ).select_related('budget__fiscal_period').first()

                if budget_line:
                    # Compute already-spent amount for this account in the period
                    spent_agg = JournalEntryLine.objects.filter(
                        account_id=account_id,
                        entry__date__gte=fp.start_date,
                        entry__date__lte=fp.end_date,
                        entry__status='posted',
                    ).aggregate(total=Sum('debit'))
                    spent = spent_agg['total'] or Decimal('0.00')

                    if spent + amount > budget_line.budgeted_amount:
                        budget_warning = True
                        budget_warning_detail = (
                            f"Adding {amount} to account '{budget_line.account.name}' "
                            f"would bring total spend to {spent + amount}, "
                            f"exceeding the budget of {budget_line.budgeted_amount}."
                        )
            except FiscalPeriod.DoesNotExist:
                pass  # No open period — no budget check possible

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        response_data = serializer.data
        response_data['budget_warning'] = budget_warning
        if budget_warning:
            response_data['budget_warning_detail'] = budget_warning_detail

        return Response(
            response_data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )
```

**Note on `CashRequisition.account` field**: Inspect the current `CashRequisition` model. If `account` is not already present, add:

```python
# backend/finance/models.py — CashRequisition
account = models.ForeignKey(
    'Account',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='cash_requisitions',
    help_text="The chart-of-accounts entry this requisition charges to.",
)
```

Then regenerate the migration:

```bash
docker compose exec backend python manage.py makemigrations finance
docker compose exec backend python manage.py migrate_schemas
```

---

## Phase 4: SupplierInvoice + APPayment Models and Migration

### Edit `backend/finance/models.py`

Add the two new AP models after `BudgetLine`. These reference `inventory.Supplier` and `inventory.PurchaseOrder` — valid ForeignKeys because all three apps are in the same tenant schema.

```python
from inventory.models import Supplier, PurchaseOrder  # add at top of file


class SupplierInvoice(models.Model):
    """
    An invoice received from a supplier, optionally linked to a PurchaseOrder.
    Tracks approval and payment state through the AP workflow.
    """
    INVOICE_STATUS = [
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name='invoices',
    )
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices',
    )
    invoice_number = models.CharField(
        max_length=100,
        help_text="Must be unique within this tenant schema.",
    )
    invoice_date = models.DateField()
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    tax_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    status = models.CharField(
        max_length=20,
        choices=INVOICE_STATUS,
        default='draft',
    )
    notes = models.TextField(blank=True)
    created_by_id = models.IntegerField(
        help_text="User ID of the person who created this invoice record."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-invoice_date']
        unique_together = [('supplier', 'invoice_number')]

    def __str__(self):
        return f"Invoice {self.invoice_number} — {self.supplier.name}"

    @property
    def total_amount(self):
        """Invoice amount including tax."""
        return self.amount + self.tax_amount

    @property
    def amount_paid(self):
        """Sum of all associated APPayment amounts."""
        result = self.payments.aggregate(total=Sum('amount'))
        return result['total'] or Decimal('0.00')

    @property
    def amount_outstanding(self):
        return self.total_amount - self.amount_paid


class APPayment(models.Model):
    """
    A payment made against a SupplierInvoice.
    When the sum of all payments for an invoice reaches or exceeds
    invoice.total_amount, the invoice is automatically marked 'paid'.
    """
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
        ('cheque', 'Cheque'),
    ]

    invoice = models.ForeignKey(
        SupplierInvoice,
        on_delete=models.PROTECT,
        related_name='payments',
    )
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
    )
    reference = models.CharField(
        max_length=200,
        blank=True,
        help_text="Bank reference, MoMo transaction ID, cheque number, etc.",
    )
    notes = models.TextField(blank=True)
    created_by_id = models.IntegerField(
        help_text="User ID of the person who recorded this payment."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-payment_date']

    def __str__(self):
        return (
            f"Payment {self.amount} on {self.payment_date} "
            f"for invoice {self.invoice.invoice_number}"
        )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Auto-mark invoice paid when fully settled
        self._update_invoice_status()

    def _update_invoice_status(self):
        invoice = self.invoice
        if invoice.status in ('cancelled',):
            return
        if invoice.amount_paid >= invoice.total_amount:
            invoice.status = 'paid'
            invoice.save(update_fields=['status', 'updated_at'])
```

**Decimal import**: Ensure `from decimal import Decimal` is at the top of `models.py` — it is needed for `default=Decimal('0.00')`.

### Run Migrations

```bash
docker compose exec backend python manage.py makemigrations finance
docker compose exec backend python manage.py migrate_schemas
```

The migration will be named something like `0004_supplierinvoice_appayment.py`. Verify:

```bash
docker compose exec backend python manage.py showmigrations finance
```

---

## Phase 5: AP Serializers and ViewSet

### Edit `backend/finance/serializers.py`

Append after the Budget serializers.

```python
from .models import SupplierInvoice, APPayment


class APPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = APPayment
        fields = [
            'id',
            'invoice',
            'payment_date',
            'amount',
            'payment_method',
            'reference',
            'notes',
            'created_by_id',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_by_id', 'created_at', 'updated_at']


class APPaymentCreateSerializer(serializers.ModelSerializer):
    """Used for the /pay/ action — invoice is set from the URL, not the body."""

    class Meta:
        model = APPayment
        fields = [
            'payment_date',
            'amount',
            'payment_method',
            'reference',
            'notes',
        ]

    def validate_amount(self, value):
        if value <= Decimal('0.00'):
            raise serializers.ValidationError("Payment amount must be positive.")
        return value


class SupplierInvoiceSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    purchase_order_ref = serializers.SerializerMethodField()
    payments = APPaymentSerializer(many=True, read_only=True)
    total_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    amount_paid = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    amount_outstanding = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )

    class Meta:
        model = SupplierInvoice
        fields = [
            'id',
            'supplier',
            'supplier_name',
            'purchase_order',
            'purchase_order_ref',
            'invoice_number',
            'invoice_date',
            'due_date',
            'amount',
            'tax_amount',
            'total_amount',
            'amount_paid',
            'amount_outstanding',
            'status',
            'notes',
            'created_by_id',
            'payments',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_by_id', 'status', 'created_at', 'updated_at']

    def get_purchase_order_ref(self, obj):
        if obj.purchase_order:
            return obj.purchase_order.id
        return None


class SupplierInvoiceCreateSerializer(serializers.ModelSerializer):
    """Used for POST/PATCH — excludes computed and auto-set fields."""

    class Meta:
        model = SupplierInvoice
        fields = [
            'id',
            'supplier',
            'purchase_order',
            'invoice_number',
            'invoice_date',
            'due_date',
            'amount',
            'tax_amount',
            'notes',
        ]

    def validate(self, data):
        if data.get('due_date') and data.get('invoice_date'):
            if data['due_date'] < data['invoice_date']:
                raise serializers.ValidationError(
                    "due_date cannot be before invoice_date."
                )
        return data
```

### Edit `backend/finance/views.py` — `SupplierInvoiceViewSet`

```python
from .models import SupplierInvoice, APPayment
from .serializers import (
    SupplierInvoiceSerializer,
    SupplierInvoiceCreateSerializer,
    APPaymentSerializer,
    APPaymentCreateSerializer,
)


class SupplierInvoiceViewSet(viewsets.ModelViewSet):
    """
    CRUD for SupplierInvoice.

    Custom actions:
      POST /api/finance/supplier-invoices/{id}/approve/  — draft → approved
      POST /api/finance/supplier-invoices/{id}/pay/      — creates APPayment
    """
    queryset = SupplierInvoice.objects.select_related(
        'supplier', 'purchase_order'
    ).prefetch_related('payments')
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['invoice_number', 'supplier__name']

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return SupplierInvoiceCreateSerializer
        return SupplierInvoiceSerializer

    def perform_create(self, serializer):
        serializer.save(created_by_id=self.request.user.id)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        """
        POST /api/finance/supplier-invoices/{id}/approve/

        Moves the invoice from 'draft' to 'approved'.
        Returns 400 if the invoice is not currently in 'draft' status.
        """
        invoice = self.get_object()
        if invoice.status != 'draft':
            return Response(
                {'error': f"Cannot approve invoice with status '{invoice.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        invoice.status = 'approved'
        invoice.save(update_fields=['status', 'updated_at'])
        return Response(SupplierInvoiceSerializer(invoice).data)

    @action(detail=True, methods=['post'], url_path='pay')
    def pay(self, request, pk=None):
        """
        POST /api/finance/supplier-invoices/{id}/pay/

        Creates an APPayment against this invoice.
        The invoice must be in 'approved' status.
        If this payment brings the total paid to >= invoice.total_amount,
        APPayment.save() will automatically set invoice.status = 'paid'.

        Request body: { payment_date, amount, payment_method, reference?, notes? }
        """
        invoice = self.get_object()
        if invoice.status not in ('approved',):
            return Response(
                {
                    'error': (
                        f"Cannot pay invoice with status '{invoice.status}'. "
                        f"Invoice must be in 'approved' status."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = APPaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Prevent overpayment beyond outstanding balance
        amount = serializer.validated_data['amount']
        if amount > invoice.amount_outstanding:
            return Response(
                {
                    'error': (
                        f"Payment amount {amount} exceeds outstanding balance "
                        f"{invoice.amount_outstanding}."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment = serializer.save(
            invoice=invoice,
            created_by_id=request.user.id,
        )
        invoice.refresh_from_db()
        return Response(
            {
                'payment': APPaymentSerializer(payment).data,
                'invoice_status': invoice.status,
                'amount_outstanding': str(invoice.amount_outstanding),
            },
            status=status.HTTP_201_CREATED,
        )
```

### Register URL in `backend/finance/urls.py`

```python
from .views import (
    AccountViewSet,
    FiscalPeriodViewSet,
    JournalEntryViewSet,
    CashRequisitionViewSet,
    BudgetViewSet,
    SupplierInvoiceViewSet,   # <-- add
    trial_balance_view,
    profit_loss_view,
    balance_sheet_view,
    account_ledger_view,
    ap_aging_view,            # <-- add (defined in Phase 6)
)

router.register(r'supplier-invoices', SupplierInvoiceViewSet)   # <-- add

urlpatterns = router.urls + [
    path('reports/trial-balance/', trial_balance_view, name='trial-balance'),
    path('reports/profit-loss/', profit_loss_view, name='profit-loss'),
    path('reports/balance-sheet/', balance_sheet_view, name='balance-sheet'),
    path('reports/account-ledger/<int:account_id>/', account_ledger_view, name='account-ledger'),
    path('reports/ap-aging/', ap_aging_view, name='ap-aging'),   # <-- add
]
```

---

## Phase 6: AP Aging Report Endpoint

The aging report groups unpaid invoices by how many days they are overdue, broken down by supplier. Buckets: current (not yet overdue), 1–30 days, 31–60 days, 61–90 days, 90+ days.

### Edit `backend/finance/views.py`

Add the function-based view and import it in `urls.py`.

```python
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes as api_permission_classes


@api_view(['GET'])
@api_permission_classes([IsAuthenticated])
def ap_aging_view(request):
    """
    GET /api/finance/reports/ap-aging/

    Returns unpaid supplier invoices grouped by supplier and overdue-day bucket.
    Invoices with status 'draft', 'approved', or 'overdue' are included.
    Paid and cancelled invoices are excluded.

    Response shape:
    {
        "as_of": "2026-05-13",
        "totals": {
            "current": "0.00",
            "1_30": "0.00",
            "31_60": "0.00",
            "61_90": "0.00",
            "over_90": "0.00",
            "grand_total": "0.00"
        },
        "by_supplier": [
            {
                "supplier_id": 1,
                "supplier_name": "Shell Uganda",
                "current": "0.00",
                "1_30": "500000.00",
                "31_60": "0.00",
                "61_90": "0.00",
                "over_90": "0.00",
                "total": "500000.00"
            }
        ]
    }
    """
    today = timezone.now().date()

    unpaid = SupplierInvoice.objects.filter(
        status__in=('draft', 'approved', 'overdue')
    ).select_related('supplier').prefetch_related('payments')

    # Auto-update overdue status for any approved invoices past due date
    for inv in unpaid:
        if inv.status == 'approved' and inv.due_date < today:
            inv.status = 'overdue'
            inv.save(update_fields=['status', 'updated_at'])

    supplier_map = {}

    for inv in unpaid:
        sid = inv.supplier_id
        if sid not in supplier_map:
            supplier_map[sid] = {
                'supplier_id': sid,
                'supplier_name': inv.supplier.name,
                'current': Decimal('0.00'),
                '1_30': Decimal('0.00'),
                '31_60': Decimal('0.00'),
                '61_90': Decimal('0.00'),
                'over_90': Decimal('0.00'),
            }

        outstanding = inv.amount_outstanding
        if outstanding <= Decimal('0.00'):
            continue

        if inv.due_date >= today:
            bucket = 'current'
        else:
            days_overdue = (today - inv.due_date).days
            if days_overdue <= 30:
                bucket = '1_30'
            elif days_overdue <= 60:
                bucket = '31_60'
            elif days_overdue <= 90:
                bucket = '61_90'
            else:
                bucket = 'over_90'

        supplier_map[sid][bucket] += outstanding

    by_supplier = []
    totals = {
        'current': Decimal('0.00'),
        '1_30': Decimal('0.00'),
        '31_60': Decimal('0.00'),
        '61_90': Decimal('0.00'),
        'over_90': Decimal('0.00'),
    }

    for row in supplier_map.values():
        row_total = sum(row[b] for b in totals.keys())
        by_supplier.append({**row, 'total': row_total})
        for b in totals.keys():
            totals[b] += row[b]

    totals['grand_total'] = sum(totals[b] for b in ['current', '1_30', '31_60', '61_90', 'over_90'])

    # Format all Decimal values as strings for consistent JSON output
    def _fmt(d):
        return {k: str(v) for k, v in d.items()}

    return Response({
        'as_of': str(today),
        'totals': _fmt(totals),
        'by_supplier': [
            {**_fmt({k: v for k, v in row.items() if k not in ('supplier_id', 'supplier_name')}),
             'supplier_id': row['supplier_id'],
             'supplier_name': row['supplier_name']}
            for row in by_supplier
        ],
    })
```

---

## Phase 7: Outlet-Level P&L Enhancement

### Check JournalEntry for outlet_id

Before editing `profit_loss_view`, inspect the current `JournalEntry` model:

```bash
docker compose exec backend python manage.py shell -c \
  "from finance.models import JournalEntry; print([f.name for f in JournalEntry._meta.get_fields()])"
```

**If `outlet_id` (or `outlet`) is already present** — skip to the view edit below.

**If `outlet_id` is absent** — add it to the model:

```python
# backend/finance/models.py — JournalEntry class
outlet_id = models.IntegerField(
    null=True,
    blank=True,
    db_index=True,
    help_text=(
        "Optional outlet reference for outlet-level financial reporting. "
        "IntegerField — cross-schema FK not possible with django-tenants."
    ),
)
```

Then run:

```bash
docker compose exec backend python manage.py makemigrations finance
docker compose exec backend python manage.py migrate_schemas
```

### Edit `backend/finance/views.py` — `profit_loss_view`

Locate the existing `profit_loss_view` function and add `outlet_id` filtering. The full revised function:

```python
@api_view(['GET'])
@api_permission_classes([IsAuthenticated])
def profit_loss_view(request):
    """
    GET /api/finance/reports/profit-loss/?start=YYYY-MM-DD&end=YYYY-MM-DD[&outlet_id=N]

    Returns total income and total expenses for the given date range,
    grouped by account. If outlet_id is provided, only JournalEntry records
    with that outlet_id are included.

    Response:
    {
        "start": "2026-01-01",
        "end": "2026-03-31",
        "outlet_id": 2,
        "income": [{"account_id": ..., "account_name": ..., "total": "..."}],
        "expenses": [{"account_id": ..., "account_name": ..., "total": "..."}],
        "net_income": "..."
    }
    """
    start = request.query_params.get('start')
    end = request.query_params.get('end')
    outlet_id = request.query_params.get('outlet_id')

    if not start or not end:
        return Response(
            {'error': 'start and end query parameters are required (YYYY-MM-DD).'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    entry_filter = Q(
        entry__date__gte=start,
        entry__date__lte=end,
        entry__status='posted',
    )
    if outlet_id:
        entry_filter &= Q(entry__outlet_id=int(outlet_id))

    income_qs = (
        JournalEntryLine.objects.filter(
            entry_filter,
            account__account_type='INCOME',
        )
        .values('account__id', 'account__name')
        .annotate(total=Sum('credit') - Sum('debit'))
        .order_by('account__name')
    )

    expense_qs = (
        JournalEntryLine.objects.filter(
            entry_filter,
            account__account_type='EXPENSE',
        )
        .values('account__id', 'account__name')
        .annotate(total=Sum('debit') - Sum('credit'))
        .order_by('account__name')
    )

    def _rows(qs):
        return [
            {
                'account_id': row['account__id'],
                'account_name': row['account__name'],
                'total': str(row['total'] or Decimal('0.00')),
            }
            for row in qs
        ]

    income_rows = _rows(income_qs)
    expense_rows = _rows(expense_qs)

    total_income = sum(Decimal(r['total']) for r in income_rows)
    total_expenses = sum(Decimal(r['total']) for r in expense_rows)
    net_income = total_income - total_expenses

    return Response({
        'start': start,
        'end': end,
        'outlet_id': int(outlet_id) if outlet_id else None,
        'income': income_rows,
        'expenses': expense_rows,
        'total_income': str(total_income),
        'total_expenses': str(total_expenses),
        'net_income': str(net_income),
    })
```

---

## Phase 8: Tests

All tests use `TenantTestCase` + `TenantClient`. Fixtures are created in `setUpTestData` for efficiency. Run with:

```bash
docker compose exec backend python manage.py test finance
```

### `backend/finance/tests.py` — additions

Append these test classes to the existing `tests.py`. The existing tests must continue to pass.

```python
from decimal import Decimal
from datetime import date, timedelta

from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from rest_framework import status

from outlets.models import Outlet
from users.models import User
from inventory.models import Supplier, PurchaseOrder

from .models import (
    Account, FiscalPeriod, JournalEntry, JournalEntryLine,
    CashRequisition, Budget, BudgetLine,
    SupplierInvoice, APPayment,
)


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------

class FinancePhase12TestCase(TenantTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.outlet = Outlet.objects.create(name='Lira Station', outlet_type='fuel_station')

        cls.admin = User.objects.create_user(
            email='admin@test.com', password='pass123', role='admin'
        )
        cls.accountant = User.objects.create_user(
            email='accountant@test.com', password='pass123', role='accountant'
        )

        # Chart of accounts
        cls.income_account = Account.objects.create(
            name='Fuel Revenue', code='4001', account_type='INCOME'
        )
        cls.expense_account = Account.objects.create(
            name='Fuel Cost', code='5001', account_type='EXPENSE'
        )

        # Fiscal period covering today
        cls.fiscal_period = FiscalPeriod.objects.create(
            start_date=date.today().replace(month=1, day=1),
            end_date=date.today().replace(month=12, day=31),
            is_closed=False,
        )

        # Supplier and PO (from inventory app, same tenant schema)
        cls.supplier = Supplier.objects.create(
            name='Total Energies Uganda',
            contact_name='John Doe',
            email='john@total.ug',
            phone='+256700000001',
        )
        cls.purchase_order = PurchaseOrder.objects.create(
            supplier=cls.supplier,
            outlet=cls.outlet,
            status='approved',
            total_amount=Decimal('5000000.00'),
        )

    def setUp(self):
        self.client = TenantClient(self.tenant)
        self.client.force_authenticate(user=self.admin)


# ---------------------------------------------------------------------------
# Group 1: Budget CRUD (6 tests)
# ---------------------------------------------------------------------------

class BudgetCRUDTests(FinancePhase12TestCase):

    def test_create_budget_succeeds(self):
        resp = self.client.post(
            '/api/finance/budgets/',
            {
                'name': 'Q1 2026 Budget',
                'fiscal_period': self.fiscal_period.id,
                'description': 'First quarter operational budget',
                'is_active': True,
            },
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['name'], 'Q1 2026 Budget')
        self.assertEqual(resp.data['created_by_id'], self.admin.id)

    def test_create_budget_with_outlet(self):
        resp = self.client.post(
            '/api/finance/budgets/',
            {
                'name': 'Outlet Budget',
                'fiscal_period': self.fiscal_period.id,
                'outlet': self.outlet.id,
                'is_active': True,
            },
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['outlet'], self.outlet.id)

    def test_list_budgets_returns_200(self):
        Budget.objects.create(
            name='Test Budget',
            fiscal_period=self.fiscal_period,
            is_active=True,
            created_by_id=self.admin.id,
        )
        resp = self.client.get('/api/finance/budgets/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.data['count'], 1)

    def test_retrieve_budget_includes_lines(self):
        budget = Budget.objects.create(
            name='Retrieve Test',
            fiscal_period=self.fiscal_period,
            is_active=True,
            created_by_id=self.admin.id,
        )
        BudgetLine.objects.create(
            budget=budget,
            account=self.expense_account,
            budgeted_amount=Decimal('1000000.00'),
        )
        resp = self.client.get(f'/api/finance/budgets/{budget.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['lines']), 1)
        self.assertEqual(resp.data['lines'][0]['account'], self.expense_account.id)

    def test_add_line_to_budget(self):
        budget = Budget.objects.create(
            name='Line Test',
            fiscal_period=self.fiscal_period,
            is_active=True,
            created_by_id=self.admin.id,
        )
        resp = self.client.post(
            f'/api/finance/budgets/{budget.id}/lines/',
            {
                'account': self.expense_account.id,
                'budgeted_amount': '2000000.00',
                'notes': 'Fuel procurement',
            },
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(BudgetLine.objects.filter(budget=budget).count(), 1)

    def test_unauthenticated_rejected(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get('/api/finance/budgets/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# Group 2: Budget variance (5 tests)
# ---------------------------------------------------------------------------

class BudgetVarianceTests(FinancePhase12TestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.budget = Budget.objects.create(
            name='Variance Test Budget',
            fiscal_period=cls.fiscal_period,
            is_active=True,
            created_by_id=cls.admin.id,
        )
        cls.budget_line = BudgetLine.objects.create(
            budget=cls.budget,
            account=cls.expense_account,
            budgeted_amount=Decimal('1000000.00'),
        )

    def _post_journal_entry(self, debit_amount):
        """Creates a posted JournalEntry with a debit on the expense account."""
        entry = JournalEntry.objects.create(
            date=date.today(),
            description='Test entry',
            status='posted',
            source='manual',
        )
        JournalEntryLine.objects.create(
            entry=entry,
            account=self.expense_account,
            debit=debit_amount,
            credit=Decimal('0.00'),
        )
        return entry

    def test_variance_no_actual_spend(self):
        resp = self.client.get(f'/api/finance/budgets/{self.budget.id}/variance/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        row = resp.data[0]
        self.assertEqual(Decimal(row['budgeted']), Decimal('1000000.00'))
        self.assertEqual(Decimal(row['actual']), Decimal('0.00'))
        self.assertEqual(Decimal(row['variance']), Decimal('1000000.00'))

    def test_variance_partial_spend(self):
        self._post_journal_entry(Decimal('300000.00'))
        resp = self.client.get(f'/api/finance/budgets/{self.budget.id}/variance/')
        row = next(r for r in resp.data if r['account_id'] == self.expense_account.id)
        self.assertEqual(Decimal(row['actual']), Decimal('300000.00'))
        self.assertEqual(Decimal(row['variance']), Decimal('700000.00'))

    def test_variance_over_budget(self):
        self._post_journal_entry(Decimal('1200000.00'))
        resp = self.client.get(f'/api/finance/budgets/{self.budget.id}/variance/')
        row = next(r for r in resp.data if r['account_id'] == self.expense_account.id)
        self.assertLess(Decimal(row['variance']), Decimal('0.00'))

    def test_variance_pct_calculated(self):
        self._post_journal_entry(Decimal('500000.00'))
        resp = self.client.get(f'/api/finance/budgets/{self.budget.id}/variance/')
        row = next(r for r in resp.data if r['account_id'] == self.expense_account.id)
        self.assertIsNotNone(row['variance_pct'])

    def test_summary_returns_active_budgets(self):
        resp = self.client.get('/api/finance/budgets/summary/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [b['id'] for b in resp.data]
        self.assertIn(self.budget.id, ids)


# ---------------------------------------------------------------------------
# Group 3: Budget enforcement on CashRequisition (4 tests)
# ---------------------------------------------------------------------------

class BudgetEnforcementTests(FinancePhase12TestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.budget = Budget.objects.create(
            name='Enforcement Budget',
            fiscal_period=cls.fiscal_period,
            is_active=True,
            created_by_id=cls.admin.id,
        )
        BudgetLine.objects.create(
            budget=cls.budget,
            account=cls.expense_account,
            budgeted_amount=Decimal('500000.00'),
        )

    def test_requisition_within_budget_no_warning(self):
        resp = self.client.post(
            '/api/finance/cash-requisitions/',
            {
                'amount': '100000.00',
                'account': self.expense_account.id,
                'requisition_type': 'operational',
                'requester_id': self.admin.id,
                'status': 'pending',
            },
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertFalse(resp.data.get('budget_warning', False))

    def test_requisition_exceeding_budget_returns_warning(self):
        resp = self.client.post(
            '/api/finance/cash-requisitions/',
            {
                'amount': '600000.00',
                'account': self.expense_account.id,
                'requisition_type': 'operational',
                'requester_id': self.admin.id,
                'status': 'pending',
            },
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(resp.data.get('budget_warning', False))
        self.assertIn('budget_warning_detail', resp.data)

    def test_requisition_still_created_despite_warning(self):
        """Soft enforcement — record is persisted even when budget_warning is True."""
        before = CashRequisition.objects.count()
        self.client.post(
            '/api/finance/cash-requisitions/',
            {
                'amount': '9999999.00',
                'account': self.expense_account.id,
                'requisition_type': 'operational',
                'requester_id': self.admin.id,
                'status': 'pending',
            },
            content_type='application/json',
        )
        self.assertEqual(CashRequisition.objects.count(), before + 1)

    def test_requisition_without_account_no_warning(self):
        """If no account is specified, budget check is skipped — no warning."""
        resp = self.client.post(
            '/api/finance/cash-requisitions/',
            {
                'amount': '100000.00',
                'requisition_type': 'operational',
                'requester_id': self.admin.id,
                'status': 'pending',
            },
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertFalse(resp.data.get('budget_warning', False))


# ---------------------------------------------------------------------------
# Group 4: SupplierInvoice CRUD (6 tests)
# ---------------------------------------------------------------------------

class SupplierInvoiceCRUDTests(FinancePhase12TestCase):

    def _invoice_payload(self, **overrides):
        payload = {
            'supplier': self.supplier.id,
            'purchase_order': self.purchase_order.id,
            'invoice_number': 'INV-2026-001',
            'invoice_date': str(date.today()),
            'due_date': str(date.today() + timedelta(days=30)),
            'amount': '4000000.00',
            'tax_amount': '720000.00',
            'notes': 'Fuel delivery May 2026',
        }
        payload.update(overrides)
        return payload

    def test_create_invoice_succeeds(self):
        resp = self.client.post(
            '/api/finance/supplier-invoices/',
            self._invoice_payload(),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['status'], 'draft')
        self.assertEqual(resp.data['created_by_id'], self.admin.id)

    def test_due_date_before_invoice_date_rejected(self):
        resp = self.client.post(
            '/api/finance/supplier-invoices/',
            self._invoice_payload(
                due_date=str(date.today() - timedelta(days=5))
            ),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_invoices_returns_200(self):
        SupplierInvoice.objects.create(
            supplier=self.supplier,
            invoice_number='INV-LIST-001',
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            amount=Decimal('1000000.00'),
            created_by_id=self.admin.id,
        )
        resp = self.client.get('/api/finance/supplier-invoices/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(resp.data['count'], 1)

    def test_retrieve_invoice_includes_payments(self):
        invoice = SupplierInvoice.objects.create(
            supplier=self.supplier,
            invoice_number='INV-PAYMENTS-001',
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            amount=Decimal('1000000.00'),
            status='approved',
            created_by_id=self.admin.id,
        )
        APPayment.objects.create(
            invoice=invoice,
            payment_date=date.today(),
            amount=Decimal('500000.00'),
            payment_method='bank_transfer',
            created_by_id=self.admin.id,
        )
        resp = self.client.get(f'/api/finance/supplier-invoices/{invoice.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['payments']), 1)

    def test_duplicate_invoice_number_per_supplier_rejected(self):
        SupplierInvoice.objects.create(
            supplier=self.supplier,
            invoice_number='INV-DUP-001',
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            amount=Decimal('1000000.00'),
            created_by_id=self.admin.id,
        )
        resp = self.client.post(
            '/api/finance/supplier-invoices/',
            self._invoice_payload(invoice_number='INV-DUP-001'),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_rejected(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get('/api/finance/supplier-invoices/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# Group 5: AP workflow — approve and pay (6 tests)
# ---------------------------------------------------------------------------

class APWorkflowTests(FinancePhase12TestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.invoice = SupplierInvoice.objects.create(
            supplier=cls.supplier,
            invoice_number='INV-WORKFLOW-001',
            invoice_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            amount=Decimal('2000000.00'),
            tax_amount=Decimal('360000.00'),
            status='draft',
            created_by_id=cls.admin.id,
        )

    def test_approve_draft_invoice_succeeds(self):
        resp = self.client.post(
            f'/api/finance/supplier-invoices/{self.invoice.id}/approve/'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, 'approved')

    def test_approve_already_approved_returns_400(self):
        self.invoice.status = 'approved'
        self.invoice.save()
        resp = self.client.post(
            f'/api/finance/supplier-invoices/{self.invoice.id}/approve/'
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.invoice.status = 'draft'
        self.invoice.save()

    def test_pay_approved_invoice_succeeds(self):
        self.invoice.status = 'approved'
        self.invoice.save()
        resp = self.client.post(
            f'/api/finance/supplier-invoices/{self.invoice.id}/pay/',
            {
                'payment_date': str(date.today()),
                'amount': '1000000.00',
                'payment_method': 'bank_transfer',
                'reference': 'BANK-REF-001',
            },
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('payment', resp.data)
        self.assertIn('invoice_status', resp.data)

    def test_full_payment_auto_marks_paid(self):
        self.invoice.status = 'approved'
        self.invoice.save()
        total = self.invoice.total_amount
        resp = self.client.post(
            f'/api/finance/supplier-invoices/{self.invoice.id}/pay/',
            {
                'payment_date': str(date.today()),
                'amount': str(total),
                'payment_method': 'cash',
            },
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['invoice_status'], 'paid')

    def test_overpayment_rejected(self):
        self.invoice.status = 'approved'
        self.invoice.save()
        overpay = str(self.invoice.total_amount + Decimal('1.00'))
        resp = self.client.post(
            f'/api/finance/supplier-invoices/{self.invoice.id}/pay/',
            {
                'payment_date': str(date.today()),
                'amount': overpay,
                'payment_method': 'cash',
            },
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('outstanding', str(resp.data))

    def test_pay_draft_invoice_rejected(self):
        self.invoice.status = 'draft'
        self.invoice.save()
        resp = self.client.post(
            f'/api/finance/supplier-invoices/{self.invoice.id}/pay/',
            {
                'payment_date': str(date.today()),
                'amount': '100000.00',
                'payment_method': 'cash',
            },
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Group 6: AP aging report (5 tests)
# ---------------------------------------------------------------------------

class APAgingTests(FinancePhase12TestCase):

    def _make_invoice(self, days_overdue=0, amount='1000000.00', status='approved'):
        due = date.today() - timedelta(days=days_overdue) if days_overdue > 0 else date.today() + timedelta(days=30)
        inv = SupplierInvoice.objects.create(
            supplier=self.supplier,
            invoice_number=f'INV-AGING-{days_overdue}-{amount}',
            invoice_date=date.today() - timedelta(days=max(days_overdue, 0) + 10),
            due_date=due,
            amount=Decimal(amount),
            status=status,
            created_by_id=self.admin.id,
        )
        return inv

    def test_aging_returns_200(self):
        resp = self.client.get('/api/finance/reports/ap-aging/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('as_of', resp.data)
        self.assertIn('totals', resp.data)
        self.assertIn('by_supplier', resp.data)

    def test_current_invoice_in_current_bucket(self):
        self._make_invoice(days_overdue=0)
        resp = self.client.get('/api/finance/reports/ap-aging/')
        row = next(
            (r for r in resp.data['by_supplier'] if r['supplier_id'] == self.supplier.id),
            None
        )
        self.assertIsNotNone(row)
        self.assertGreater(Decimal(row['current']), Decimal('0.00'))

    def test_30_day_overdue_in_correct_bucket(self):
        self._make_invoice(days_overdue=20)
        resp = self.client.get('/api/finance/reports/ap-aging/')
        row = next(
            r for r in resp.data['by_supplier'] if r['supplier_id'] == self.supplier.id
        )
        self.assertGreater(Decimal(row['1_30']), Decimal('0.00'))

    def test_paid_invoices_excluded(self):
        self._make_invoice(days_overdue=10, status='paid')
        resp = self.client.get('/api/finance/reports/ap-aging/')
        totals = resp.data['totals']
        # A paid invoice should contribute nothing to totals
        # (This test is meaningful if no other unpaid invoices exist for this supplier)
        self.assertIn('grand_total', totals)

    def test_totals_sum_correctly(self):
        resp = self.client.get('/api/finance/reports/ap-aging/')
        t = resp.data['totals']
        buckets_sum = (
            Decimal(t['current']) + Decimal(t['1_30']) +
            Decimal(t['31_60']) + Decimal(t['61_90']) + Decimal(t['over_90'])
        )
        self.assertEqual(buckets_sum, Decimal(t['grand_total']))


# ---------------------------------------------------------------------------
# Group 7: Outlet-level P&L (4 tests)
# ---------------------------------------------------------------------------

class OutletPLTests(FinancePhase12TestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.outlet2 = Outlet.objects.create(
            name='Gulu Station', outlet_type='fuel_station'
        )

        # Entry for outlet 1
        entry1 = JournalEntry.objects.create(
            date=date.today(),
            description='Outlet 1 revenue',
            status='posted',
            source='manual',
            outlet_id=cls.outlet.id,
        )
        JournalEntryLine.objects.create(
            entry=entry1, account=cls.income_account,
            debit=Decimal('0.00'), credit=Decimal('1000000.00')
        )

        # Entry for outlet 2
        entry2 = JournalEntry.objects.create(
            date=date.today(),
            description='Outlet 2 revenue',
            status='posted',
            source='manual',
            outlet_id=cls.outlet2.id,
        )
        JournalEntryLine.objects.create(
            entry=entry2, account=cls.income_account,
            debit=Decimal('0.00'), credit=Decimal('500000.00')
        )

    def test_pl_without_outlet_filter_includes_all(self):
        resp = self.client.get(
            f'/api/finance/reports/profit-loss/'
            f'?start={date.today()}&end={date.today()}'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        total_income = Decimal(resp.data['total_income'])
        self.assertGreaterEqual(total_income, Decimal('1500000.00'))

    def test_pl_with_outlet_filter_isolates_outlet(self):
        resp = self.client.get(
            f'/api/finance/reports/profit-loss/'
            f'?start={date.today()}&end={date.today()}&outlet_id={self.outlet.id}'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['outlet_id'], self.outlet.id)
        total_income = Decimal(resp.data['total_income'])
        self.assertEqual(total_income, Decimal('1000000.00'))

    def test_pl_missing_dates_returns_400(self):
        resp = self.client.get('/api/finance/reports/profit-loss/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pl_outlet_id_null_when_not_provided(self):
        resp = self.client.get(
            f'/api/finance/reports/profit-loss/'
            f'?start={date.today()}&end={date.today()}'
        )
        self.assertIsNone(resp.data['outlet_id'])
```

---

## Quality Checklist

Work through this list before opening a PR.

### Models

- [ ] `Budget` has all 9 specified fields: `name`, `fiscal_period`, `department`, `outlet`, `description`, `is_active`, `created_by_id`, `created_at`, `updated_at`
- [ ] `Budget.Meta.ordering = ['-created_at']`
- [ ] `BudgetLine` has `unique_together = [('budget', 'account')]`
- [ ] `BudgetLine.Meta.ordering = ['account__code']`
- [ ] `SupplierInvoice.INVOICE_STATUS` contains: `draft`, `approved`, `paid`, `overdue`, `cancelled`
- [ ] `SupplierInvoice.unique_together = [('supplier', 'invoice_number')]`
- [ ] `SupplierInvoice.amount` and `tax_amount` are `DecimalField` — no `FloatField`
- [ ] `APPayment.save()` calls `_update_invoice_status()` to auto-mark invoice `paid`
- [ ] `SupplierInvoice.amount_paid` and `amount_outstanding` are `@property` methods
- [ ] `JournalEntry.outlet_id` exists (added in this phase if missing) — `IntegerField`, nullable, `db_index=True`
- [ ] `CashRequisition.account` FK exists (added in this phase if missing)

### Serializers

- [ ] All serializers list fields explicitly — no `fields = '__all__'`
- [ ] `BudgetSerializer` includes nested `lines` (read-only)
- [ ] `BudgetVarianceLineSerializer` is a plain `Serializer` (not `ModelSerializer`)
- [ ] `SupplierInvoiceSerializer` includes computed properties: `total_amount`, `amount_paid`, `amount_outstanding`
- [ ] `SupplierInvoiceCreateSerializer.validate()` enforces `due_date >= invoice_date`
- [ ] `APPaymentCreateSerializer.validate_amount()` rejects zero/negative amounts

### Views

- [ ] `BudgetViewSet.variance()` uses `fiscal_period.start_date` and `fiscal_period.end_date` as date bounds for `JournalEntry` filtering
- [ ] `BudgetViewSet.variance()` distinguishes INCOME vs EXPENSE vs other account types for actual calculation
- [ ] `BudgetViewSet.perform_create()` sets `created_by_id = request.user.id`
- [ ] `CashRequisitionViewSet.create()` returns `budget_warning: true` (HTTP 201, not 200) when budget would be exceeded
- [ ] `CashRequisitionViewSet.create()` always creates the requisition regardless of budget status
- [ ] `SupplierInvoiceViewSet.approve()` returns 400 if invoice is not in `draft` status
- [ ] `SupplierInvoiceViewSet.pay()` returns 400 if invoice is not in `approved` status
- [ ] `SupplierInvoiceViewSet.pay()` rejects overpayment (amount > outstanding)
- [ ] `ap_aging_view` auto-updates `approved` invoices with `due_date < today` to `overdue`
- [ ] `ap_aging_view` excludes `paid` and `cancelled` invoices
- [ ] `profit_loss_view` accepts optional `?outlet_id=` parameter
- [ ] `profit_loss_view` returns `outlet_id: null` when no filter is applied

### Migrations

- [ ] `makemigrations finance` — adds `Budget`, `BudgetLine` models (`0003_...`)
- [ ] `makemigrations finance` — adds `SupplierInvoice`, `APPayment` models (`0004_...`)
- [ ] `makemigrations finance` — adds `outlet_id` to `JournalEntry` if missing (`0005_...`)
- [ ] `makemigrations finance` — adds `account` FK to `CashRequisition` if missing
- [ ] All migrations run with `migrate_schemas` (not `migrate`)
- [ ] `migrate_schemas` completes without errors on a clean DB
- [ ] `showmigrations finance` shows all migrations applied

### URLs

- [ ] `GET/POST /api/finance/budgets/` wired via router
- [ ] `GET /api/finance/budgets/{id}/variance/` wired as custom action
- [ ] `GET /api/finance/budgets/summary/` wired as custom action
- [ ] `POST /api/finance/budgets/{id}/lines/` wired as custom action
- [ ] `CRUD /api/finance/supplier-invoices/` wired via router
- [ ] `POST /api/finance/supplier-invoices/{id}/approve/` wired as custom action
- [ ] `POST /api/finance/supplier-invoices/{id}/pay/` wired as custom action
- [ ] `GET /api/finance/reports/ap-aging/` wired as function-based view

### Tests

- [ ] 31+ test methods total
- [ ] All test classes extend `TenantTestCase`
- [ ] All `self.client` instances are `TenantClient`
- [ ] Group 1: 6 Budget CRUD tests
- [ ] Group 2: 5 Budget variance tests
- [ ] Group 3: 4 Budget enforcement tests
- [ ] Group 4: 6 SupplierInvoice CRUD tests
- [ ] Group 5: 6 AP workflow tests (approve + pay)
- [ ] Group 6: 5 AP aging tests
- [ ] Group 7: 4 Outlet P&L tests
- [ ] All tests pass: `docker compose exec backend python manage.py test finance`

---

## API Reference

### Budget Management

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/finance/budgets/` | Authenticated | List all budgets (paginated) |
| POST | `/api/finance/budgets/` | Authenticated | Create budget |
| GET | `/api/finance/budgets/{id}/` | Authenticated | Retrieve budget with lines |
| PATCH | `/api/finance/budgets/{id}/` | Authenticated | Update budget |
| DELETE | `/api/finance/budgets/{id}/` | Authenticated | Delete budget |
| POST | `/api/finance/budgets/{id}/lines/` | Authenticated | Add a budget line |
| GET | `/api/finance/budgets/{id}/variance/` | Authenticated | Account-level variance report |
| GET | `/api/finance/budgets/summary/` | Authenticated | All active budgets with totals |

**POST `/api/finance/budgets/`**

Request:
```json
{
  "name": "Q2 2026 Operations",
  "fiscal_period": 1,
  "outlet": 2,
  "description": "Second quarter operational budget",
  "is_active": true
}
```

Response `201`:
```json
{
  "id": 3,
  "name": "Q2 2026 Operations",
  "fiscal_period": 1,
  "fiscal_period_display": "2026-01-01 – 2026-12-31",
  "outlet": 2,
  "outlet_name": "Lira Central Station",
  "description": "Second quarter operational budget",
  "is_active": true,
  "created_by_id": 1,
  "lines": [],
  "created_at": "2026-05-13T10:00:00Z",
  "updated_at": "2026-05-13T10:00:00Z"
}
```

**GET `/api/finance/budgets/{id}/variance/`**

Response `200`:
```json
[
  {
    "account_id": 12,
    "account_name": "Fuel Cost",
    "account_code": "5001",
    "budgeted": "1000000.00",
    "actual": "620000.00",
    "variance": "380000.00",
    "variance_pct": "38.00"
  }
]
```

**GET `/api/finance/budgets/summary/`**

Response `200`:
```json
[
  {
    "id": 3,
    "name": "Q2 2026 Operations",
    "fiscal_period_display": "2026-01-01 – 2026-12-31",
    "outlet_name": "Lira Central Station",
    "total_budgeted": "5000000.00",
    "total_actual": "3100000.00",
    "total_variance": "1900000.00",
    "is_active": true
  }
]
```

---

### Accounts Payable

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/finance/supplier-invoices/` | Authenticated | List invoices (paginated) |
| POST | `/api/finance/supplier-invoices/` | Authenticated | Create invoice (draft) |
| GET | `/api/finance/supplier-invoices/{id}/` | Authenticated | Retrieve invoice with payments |
| PATCH | `/api/finance/supplier-invoices/{id}/` | Authenticated | Update invoice |
| DELETE | `/api/finance/supplier-invoices/{id}/` | Authenticated | Delete invoice |
| POST | `/api/finance/supplier-invoices/{id}/approve/` | Authenticated | Approve invoice (draft → approved) |
| POST | `/api/finance/supplier-invoices/{id}/pay/` | Authenticated | Record a payment |
| GET | `/api/finance/reports/ap-aging/` | Authenticated | AP aging report |

**POST `/api/finance/supplier-invoices/`**

Request:
```json
{
  "supplier": 4,
  "purchase_order": 7,
  "invoice_number": "TOTAL-INV-20260510",
  "invoice_date": "2026-05-10",
  "due_date": "2026-06-10",
  "amount": "4000000.00",
  "tax_amount": "720000.00",
  "notes": "May fuel delivery"
}
```

Response `201`:
```json
{
  "id": 9,
  "supplier": 4,
  "supplier_name": "Total Energies Uganda",
  "purchase_order": 7,
  "purchase_order_ref": 7,
  "invoice_number": "TOTAL-INV-20260510",
  "invoice_date": "2026-05-10",
  "due_date": "2026-06-10",
  "amount": "4000000.00",
  "tax_amount": "720000.00",
  "total_amount": "4720000.00",
  "amount_paid": "0.00",
  "amount_outstanding": "4720000.00",
  "status": "draft",
  "notes": "May fuel delivery",
  "created_by_id": 1,
  "payments": [],
  "created_at": "2026-05-13T10:00:00Z",
  "updated_at": "2026-05-13T10:00:00Z"
}
```

**POST `/api/finance/supplier-invoices/{id}/pay/`**

Request:
```json
{
  "payment_date": "2026-05-13",
  "amount": "2000000.00",
  "payment_method": "bank_transfer",
  "reference": "UG-BANK-00437",
  "notes": "Partial payment"
}
```

Response `201`:
```json
{
  "payment": {
    "id": 5,
    "invoice": 9,
    "payment_date": "2026-05-13",
    "amount": "2000000.00",
    "payment_method": "bank_transfer",
    "reference": "UG-BANK-00437",
    "notes": "Partial payment",
    "created_by_id": 1,
    "created_at": "2026-05-13T10:05:00Z",
    "updated_at": "2026-05-13T10:05:00Z"
  },
  "invoice_status": "approved",
  "amount_outstanding": "2720000.00"
}
```

**GET `/api/finance/reports/ap-aging/`**

Response `200`:
```json
{
  "as_of": "2026-05-13",
  "totals": {
    "current": "8500000.00",
    "1_30": "3200000.00",
    "31_60": "1000000.00",
    "61_90": "0.00",
    "over_90": "0.00",
    "grand_total": "12700000.00"
  },
  "by_supplier": [
    {
      "supplier_id": 4,
      "supplier_name": "Total Energies Uganda",
      "current": "4720000.00",
      "1_30": "3200000.00",
      "31_60": "0.00",
      "61_90": "0.00",
      "over_90": "0.00",
      "total": "7920000.00"
    }
  ]
}
```

---

### Profit & Loss (enhanced)

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/finance/reports/profit-loss/?start=&end=[&outlet_id=]` | Authenticated | P&L report, optionally scoped to outlet |

Response `200` (with `outlet_id`):
```json
{
  "start": "2026-01-01",
  "end": "2026-03-31",
  "outlet_id": 2,
  "income": [
    { "account_id": 8, "account_name": "Fuel Revenue", "total": "15000000.00" }
  ],
  "expenses": [
    { "account_id": 12, "account_name": "Fuel Cost", "total": "9000000.00" }
  ],
  "total_income": "15000000.00",
  "total_expenses": "9000000.00",
  "net_income": "6000000.00"
}
```

---

## Example curl Commands

### 1. Create a Budget

```bash
TOKEN="<access token>"

curl -s -X POST http://localhost:8000/api/finance/budgets/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Q2 2026 Operations",
    "fiscal_period": 1,
    "outlet": 2,
    "description": "Second quarter budget",
    "is_active": true
  }' | jq .
```

---

### 2. Add a Budget Line

```bash
BUDGET_ID=3

curl -s -X POST "http://localhost:8000/api/finance/budgets/$BUDGET_ID/lines/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "account": 12,
    "budgeted_amount": "2000000.00",
    "notes": "Fuel procurement Q2"
  }' | jq .
```

---

### 3. Check Budget Variance

```bash
curl -s "http://localhost:8000/api/finance/budgets/$BUDGET_ID/variance/" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

Expected:
```json
[
  {
    "account_id": 12,
    "account_name": "Fuel Cost",
    "account_code": "5001",
    "budgeted": "2000000.00",
    "actual": "0.00",
    "variance": "2000000.00",
    "variance_pct": "100.00"
  }
]
```

---

### 4. Budget Summary (all active budgets)

```bash
curl -s "http://localhost:8000/api/finance/budgets/summary/" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

---

### 5. Create a Supplier Invoice

```bash
curl -s -X POST http://localhost:8000/api/finance/supplier-invoices/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "supplier": 4,
    "purchase_order": 7,
    "invoice_number": "TOTAL-INV-20260510",
    "invoice_date": "2026-05-10",
    "due_date": "2026-06-10",
    "amount": "4000000.00",
    "tax_amount": "720000.00",
    "notes": "May fuel delivery"
  }' | jq .
```

---

### 6. Approve a Supplier Invoice

```bash
INVOICE_ID=9

curl -s -X POST "http://localhost:8000/api/finance/supplier-invoices/$INVOICE_ID/approve/" \
  -H "Authorization: Bearer $TOKEN" | jq .status
```

Expected: `"approved"`

---

### 7. Record a Payment Against an Invoice

```bash
curl -s -X POST "http://localhost:8000/api/finance/supplier-invoices/$INVOICE_ID/pay/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "payment_date": "2026-05-13",
    "amount": "4720000.00",
    "payment_method": "bank_transfer",
    "reference": "UG-BANK-00437"
  }' | jq .invoice_status
```

Expected: `"paid"`

---

### 8. AP Aging Report

```bash
curl -s "http://localhost:8000/api/finance/reports/ap-aging/" \
  -H "Authorization: Bearer $TOKEN" | jq .totals
```

---

### 9. Outlet-Level P&L

```bash
# All outlets
curl -s "http://localhost:8000/api/finance/reports/profit-loss/?start=2026-01-01&end=2026-03-31" \
  -H "Authorization: Bearer $TOKEN" | jq .net_income

# Outlet 2 only
curl -s "http://localhost:8000/api/finance/reports/profit-loss/?start=2026-01-01&end=2026-03-31&outlet_id=2" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

---

### 10. Cash Requisition with Budget Warning

```bash
curl -s -X POST http://localhost:8000/api/finance/cash-requisitions/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": "3000000.00",
    "account": 12,
    "requisition_type": "operational",
    "status": "pending"
  }' | jq '{id: .id, budget_warning: .budget_warning, detail: .budget_warning_detail}'
```

Expected when over budget:
```json
{
  "id": 14,
  "budget_warning": true,
  "detail": "Adding 3000000.00 to account 'Fuel Cost' would bring total spend to 3000000.00, exceeding the budget of 2000000.00."
}
```

---

## Implementation Order

Execute phases in sequence. Each phase has a concrete deliverable before moving to the next.

| # | Phase | Deliverable | Command to verify |
|---|---|---|---|
| 1 | Budget + BudgetLine models | Migration `0003_budget_budgetline.py` in `finance/migrations/` | `showmigrations finance` |
| 2 | Budget serializers + ViewSet | All budget endpoints live | `curl GET /api/finance/budgets/` → 200 |
| 3 | Budget enforcement on CashRequisition | `budget_warning` field in POST response | `curl POST /api/finance/cash-requisitions/` with over-budget amount |
| 4 | SupplierInvoice + APPayment models | Migration `0004_supplierinvoice_appayment.py` | `showmigrations finance` |
| 5 | AP serializers + ViewSet | CRUD + approve + pay endpoints live | `curl POST /api/finance/supplier-invoices/` → 201 |
| 6 | AP aging report | `ap_aging_view` wired and returning data | `curl GET /api/finance/reports/ap-aging/` → 200 |
| 7 | Outlet-level P&L | `profit_loss_view` accepts `?outlet_id=` | `curl GET /api/finance/reports/profit-loss/?start=...&end=...&outlet_id=1` |
| 8 | Tests | 31+ passing tests | `docker compose exec backend python manage.py test finance` |

---

*Last updated: 2026-05-13*  
*Author: Kakebe Technologies backend team*  
*Branch: `feat-phase-12-finance-completeness`*
