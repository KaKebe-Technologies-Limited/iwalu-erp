# Phase 7b Implementation Plan: SaaS Operations & Subscription Billing

**Backend only** (shared schema + `tenants` app extension)  
**Estimated scope**: 4–5 models, 8–10 endpoints, ~50 tests  
**New apps**: None (extend `tenants` app + add `billing` views to `api`)  
**Tenant-scoped**: No (shared schema only)

---

## Overview

Implements multi-tenant SaaS billing:
1. Subscription plans (admin configures; public can view)
2. Tenant subscription lifecycle (trial → active → suspended → cancelled)
3. Automatic invoice generation at billing cycle start
4. Tenant suspension if payment overdue (configurable days grace period)
5. Resend verification email (known limitation from Phase 7a)
6. Rate limiting on tenant registration endpoint (prevent spam/abuse)

---

## Models

### `SubscriptionPlan` (in `tenants/models.py`)

```python
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
        return f"{self.name} (${self.price_monthly}/mo, {self.max_users} users)"

    def monthly_cost(self):
        return self.price_monthly

    def annual_cost(self):
        return self.price_annual

    def monthly_equivalent(self):
        """For comparison: annual price / 12."""
        return self.price_annual / Decimal('12')
```

### `TenantSubscription` (in `tenants/models.py`)

```python
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
```

### `SubscriptionInvoice` (in `tenants/models.py`)

```python
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
```

---

## Endpoints

### Public (no auth required)

#### `GET /api/billing/plans/`

List all active plans. Public pricing endpoint.

**Response (200 OK)**:
```json
{
  "count": 3,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "slug": "starter",
      "name": "Starter",
      "price_monthly": 50000,
      "price_annual": 500000,
      "max_users": 5,
      "max_outlets": 1,
      "features": ["pos", "inventory"],
      "description": "Perfect for single-outlet fuel stations",
      "monthly_equivalent": 41667  // for comparison
    },
    ...
  ]
}
```

---

### Authenticated (Bearer token required)

#### `GET /api/billing/my-subscription/`

Current tenant's subscription status. Scoped to the request's tenant.

**Permissions**: `IsAuthenticated`

**Response (200 OK)**:
```json
{
  "id": 5,
  "tenant": "acmefuels",
  "plan": {
    "id": 2,
    "name": "Professional",
    "price_monthly": 200000
  },
  "billing_cycle": "monthly",
  "status": "active",
  "is_trial": false,
  "trial_days_remaining": 0,
  "current_period_start": "2026-03-01",
  "current_period_end": "2026-04-01",
  "next_billing_date": "2026-04-01",
  "failed_payments": 0,
  "can_upgrade": true
}
```

---

#### `POST /api/billing/my-subscription/change-plan/`

Upgrade/downgrade subscription plan.

**Permissions**: `IsAuthenticated` + admin/manager role only

**Request body**:
```json
{
  "plan_id": 3,
  "billing_cycle": "annual"
}
```

**Response (200 OK)**:
```json
{
  "status": "success",
  "new_plan": "Professional",
  "billing_cycle": "annual",
  "new_monthly_equivalent": 41667,
  "effective_date": "2026-04-01"
}
```

**Errors**:
- 400: Plan not found, billing_cycle invalid, or subscription cannot be upgraded
- 403: Only admin/manager can upgrade
- 412: Trial not yet started

---

#### `GET /api/billing/my-subscription/invoices/`

Billing history for current tenant. Paginated, ordered by period_end desc.

**Permissions**: `IsAuthenticated` + admin/manager

**Query params**:
- `status` — filter by status (pending, paid, overdue, cancelled)
- `page` — pagination

**Response (200 OK)**:
```json
{
  "count": 12,
  "results": [
    {
      "id": 48,
      "invoice_number": "INV-2026-00048",
      "period_start": "2026-03-01",
      "period_end": "2026-04-01",
      "amount": 200000,
      "status": "pending",
      "issued_at": "2026-02-28T10:00:00Z",
      "due_date": "2026-03-14",
      "paid_at": null,
      "is_overdue": false
    }
  ]
}
```

---

#### `POST /api/tenants/resend-verification/` [NEW ENDPOINT — Phase 7a gap]

Resend verification email for admin who hasn't verified yet.

**Permissions**: Public (no auth, but email must be registered)

**Request body**:
```json
{
  "email": "owner@acmefuels.com"
}
```

**Response (200 OK)**:
```json
{
  "status": "success",
  "message": "Verification email resent to owner@acmefuels.com. Check your email."
}
```

**Errors**:
- 400: Email not found or admin already verified
- 429: Rate limited (max 3 resends per email per day)

---

### Admin only (IsAdminUser permission class)

#### `GET /api/admin/billing/plans/`

List all plans (including inactive).

**Permissions**: `IsAdminUser`

---

#### `POST /api/admin/billing/plans/`

Create new subscription plan.

**Permissions**: `IsAdminUser`

**Request body**:
```json
{
  "name": "Enterprise",
  "slug": "enterprise",
  "price_monthly": 500000,
  "price_annual": 5000000,
  "max_users": 100,
  "max_outlets": 50,
  "features": ["pos", "inventory", "fuel", "hr", "accounting", "asset_management"],
  "is_active": true,
  "display_order": 3
}
```

---

#### `PATCH /api/admin/billing/plans/{id}/`

Update plan.

**Permissions**: `IsAdminUser`

---

#### `GET /api/admin/billing/subscriptions/`

List all tenant subscriptions. Filterable by status.

**Permissions**: `IsAdminUser`

**Query params**:
- `status` — trial, active, suspended, cancelled
- `plan_id` — filter by plan
- `search` — search by tenant name

**Response (200 OK)**:
```json
{
  "count": 45,
  "results": [
    {
      "id": 5,
      "tenant": "acmefuels",
      "plan": "Professional",
      "status": "active",
      "current_period_end": "2026-04-01",
      "next_billing_date": "2026-04-01",
      "failed_payments": 0,
      "suspended_reason": null
    }
  ]
}
```

---

#### `POST /api/admin/billing/subscriptions/{id}/suspend/`

Manually suspend a tenant (e.g., payment fraud, TOS violation).

**Permissions**: `IsAdminUser`

**Request body**:
```json
{
  "reason": "Payment method declined; contact tenant for update."
}
```

**Response (200 OK)**:
```json
{
  "status": "suspended",
  "reason": "Payment method declined; contact tenant for update.",
  "suspended_at": "2026-04-27T14:30:00Z"
}
```

---

#### `POST /api/admin/billing/subscriptions/{id}/reactivate/`

Reactivate a suspended tenant.

**Permissions**: `IsAdminUser`

---

#### `GET /api/admin/billing/metrics/`

SaaS dashboard metrics (MRR, ARR, churn, tenant count).

**Permissions**: `IsAdminUser`

**Response (200 OK)**:
```json
{
  "total_tenants": 45,
  "active_subscriptions": 42,
  "trialing": 3,
  "suspended": 2,
  "monthly_recurring_revenue": 8500000,
  "annual_recurring_revenue": 102000000,
  "churn_rate_30d": 2.3,
  "new_signups_30d": 8,
  "revenue_by_plan": {
    "starter": 1500000,
    "professional": 5000000,
    "enterprise": 2000000
  }
}
```

---

## Configuration

Add to `.env`:

```bash
# Subscription settings
TRIAL_DAYS=14
INVOICE_DUE_DAYS=14
PAYMENT_GRACE_PERIOD_DAYS=7  # Days past due before suspension
REGISTRATION_RATE_LIMIT=5/h   # Max registrations per hour per IP (django-ratelimit)
RECAPTCHA_ENABLED=False       # For production; use django-recaptcha
RECAPTCHA_SITE_KEY=<your-key>
RECAPTCHA_SECRET_KEY=<your-key>
```

---

## Management Commands

### `check_overdue_subscriptions`

Run daily via cron. Suspends tenants with overdue invoices past grace period.

```bash
docker compose exec backend python manage.py check_overdue_subscriptions
```

**Logic**:
1. Find invoices with `status=pending` and `due_date < today - PAYMENT_GRACE_PERIOD_DAYS`
2. Mark invoice status as `overdue`
3. Check subscription: if all recent invoices are overdue, suspend
4. Log suspension reason and send admin alert email
5. Email tenant: "Your account has been suspended due to unpaid invoice #{invoice_number}"

**File**: `tenants/management/commands/check_overdue_subscriptions.py`

---

### `generate_invoices`

Run daily at 00:00 UTC. Creates invoices for subscriptions entering a new billing cycle.

```bash
docker compose exec backend python manage.py generate_invoices
```

**Logic**:
1. Find subscriptions where `next_billing_date <= today`
2. Calculate next period: `period_start = next_billing_date`, `period_end = period_start + (30 or 365 days)`
3. Determine amount: monthly or annual price based on `billing_cycle`
4. Create `SubscriptionInvoice` with status `pending`
5. Update subscription: `current_period_start`, `current_period_end`, `next_billing_date`
6. Send email to admin: "Invoice #{invoice_number} for {amount} due {due_date}"

**File**: `tenants/management/commands/generate_invoices.py`

---

## Security & Validation

1. **Tenant isolation**: All `/api/billing/my-*` endpoints validate that request.tenant matches the subscription tenant
2. **Rate limiting** on registration:
   - Add `@ratelimit(key='ip', rate='5/h')` to registration endpoint or use middleware
   - Return 429 if exceeded
3. **CAPTCHA** (optional for Phase 7b, required for Phase 7b+ public launch):
   - Install `django-recaptcha`
   - Add to registration form; verify token before creating tenant
4. **Input validation**:
   - Plan IDs must exist and be active
   - `billing_cycle` must be 'monthly' or 'annual'
   - Dates must be in future
5. **Permission checks**:
   - Only admin/manager of a tenant can view/change subscription
   - Only global admin can view all subscriptions + manage plans

---

## Tests (50+ test cases)

### Location: `tenants/tests.py`

#### SubscriptionPlan Tests
- [ ] `test_create_plan_validates_price` — negative price rejected
- [ ] `test_plan_slug_unique` — slug uniqueness enforced
- [ ] `test_monthly_equivalent_calculation` — annual/12 calculated correctly
- [ ] `test_plan_feature_list_json` — features stored and retrieved as list

#### TenantSubscription Tests
- [ ] `test_subscription_created_with_trial_on_register` — tenant gets trial subscription
- [ ] `test_is_trial_active_true_within_trial_period` — returns True during trial
- [ ] `test_is_trial_active_false_after_expiry` — returns False when trial_days exceeded
- [ ] `test_can_upgrade_returns_true_if_active_or_trial` — upgrade blocked if suspended
- [ ] `test_suspend_updates_status_and_timestamp` — suspend() method works
- [ ] `test_reactivate_clears_suspended_state` — reactivate() works
- [ ] `test_failed_payment_count_increments` — tracks payment failures
- [ ] `test_unique_tenant_subscription` — only one sub per tenant

#### SubscriptionInvoice Tests
- [ ] `test_invoice_number_auto_generated` — INV-YYYY-##### format
- [ ] `test_invoice_unique_per_subscription_per_period` — same period twice rejected
- [ ] `test_is_overdue_true_when_past_due_date` — property works
- [ ] `test_is_overdue_false_if_paid` — paid invoices never overdue
- [ ] `test_mark_paid_sets_paid_at` — mark_paid() timestamp
- [ ] `test_invoice_amount_matches_plan_price` — billing logic correct

#### Endpoint Tests
- [ ] `test_list_plans_public_no_auth` — GET /api/billing/plans/ works unauthenticated
- [ ] `test_list_plans_excludes_inactive` — is_active=False filtered out
- [ ] `test_list_plans_sorted_by_display_order` — correct sort order
- [ ] `test_my_subscription_requires_auth` — 401 if not authenticated
- [ ] `test_my_subscription_scoped_to_tenant` — cross-tenant access blocked
- [ ] `test_change_plan_updates_subscription` — plan change persists
- [ ] `test_change_plan_requires_manager_role` — cashier/attendant blocked (403)
- [ ] `test_change_plan_trial_not_yet_started_rejected` — 412 if trial never started
- [ ] `test_invoices_list_paginated` — pagination works
- [ ] `test_invoices_filter_by_status` — status filter works
- [ ] `test_resend_verification_email_throttled` — 429 after 3 attempts/day
- [ ] `test_resend_verification_email_admin_already_verified_rejected` — 400 if verified
- [ ] `test_admin_list_plans_includes_inactive` — admin sees all plans
- [ ] `test_admin_create_plan_validates_slug` — slug validation
- [ ] `test_admin_list_subscriptions_all_statuses` — admin sees all subs
- [ ] `test_admin_list_subscriptions_filter_by_status` — status filter works
- [ ] `test_admin_suspend_subscription` — suspension persists and reason logged
- [ ] `test_admin_reactivate_subscription` — reactivation clears suspension
- [ ] `test_admin_metrics_mrr_calculation` — MRR = sum(active subscriptions) monthly prices
- [ ] `test_admin_metrics_arr_calculation` — ARR similar
- [ ] `test_admin_metrics_churn_rate` — (canceled_30d / start_30d) * 100

#### Management Command Tests
- [ ] `test_generate_invoices_creates_for_due_subscriptions` — invoices created when due
- [ ] `test_generate_invoices_skips_suspended_tenants` — suspended = no invoice
- [ ] `test_generate_invoices_monthly_vs_annual` — correct amount per cycle
- [ ] `test_generate_invoices_next_billing_date_updated` — next date calculated right
- [ ] `test_check_overdue_subscriptions_suspends_past_grace` — suspension logic
- [ ] `test_check_overdue_subscriptions_skips_paid_invoices` — doesn't suspend if paid
- [ ] `test_check_overdue_subscriptions_respects_grace_period` — waits N days before suspend

#### Integration Tests
- [ ] `test_tenant_registration_creates_subscription` — tenant created → subscription created
- [ ] `test_trial_subscription_has_correct_dates` — trial_started_at = now, period_end = now + 14 days
- [ ] `test_post_trial_conversion_to_paid` — on trial end, subscription transitions correctly
- [ ] `test_suspended_tenant_cannot_login` — 403 Forbidden if tenant suspended (check in auth middleware)
- [ ] `test_suspended_tenant_reactivation_restores_access` — can login again after reactivate

---

## Quality Checklist

Before marking as complete:

### Code Quality
- [ ] No hardcoded values; all config in .env or settings.py
- [ ] All models have `ordering`, `__str__`, `Meta.indexes` where appropriate
- [ ] Serializers separate Create/Update from Read where needed
- [ ] ViewSets use `get_serializer_class()` for action-based serializer switching
- [ ] All decimals are `Decimal()` not `float`
- [ ] Timezone-aware datetimes (use `timezone.now()` not `datetime.now()`)

### Security
- [ ] All endpoints checked with `security-reviewer` agent
- [ ] Tenant isolation verified (no cross-tenant access)
- [ ] Rate limiting on registration endpoint working
- [ ] Admin endpoints require `IsAdminUser` permission
- [ ] Input validation: plan IDs, billing cycles, dates all validated
- [ ] No SQL injection (all ORM queries, no raw SQL)
- [ ] Sensitive data (payment details) never logged

### Testing
- [ ] 50+ tests in `tenants/tests.py`
- [ ] All tests pass: `docker compose exec backend python manage.py test tenants`
- [ ] Test coverage for both happy path + error cases
- [ ] Management commands tested

### Documentation
- [ ] Docstrings on all models
- [ ] Inline comments for non-obvious logic (e.g., why trial_days is configurable)
- [ ] Create `docs/modules/billing.md` documenting:
  - Plan structure
  - Subscription lifecycle
  - Invoice generation logic
  - Endpoint reference
  - Configuration options

### Integration
- [ ] No errors in `docker compose logs backend` during test runs
- [ ] All endpoints return correct status codes
- [ ] Serialized dates in ISO-8601 format (YYYY-MM-DDTHH:MM:SSZ)
- [ ] Paginated responses follow pattern: `{count, next, previous, results}`
- [ ] Invoice emails send (or console-log in dev)

### Deployment
- [ ] Migration file created and tested: `tenants/migrations/000X_add_billing_models.py`
- [ ] Run migration: `docker compose exec backend python manage.py migrate_schemas`
- [ ] No migration errors in any schema
- [ ] Management commands run without errors

---

## Traps to Avoid

1. **Datetime timezone issues**: Always use `timezone.now()` not `datetime.now()`. Store all times in UTC.
2. **Decimal precision**: Use `Decimal()` for prices, not floats. `50000.25` stored as string becomes `Decimal('50000.25')`.
3. **Cross-tenant access**: Every `/my-subscription` endpoint must validate `subscription.tenant == request.tenant`.
4. **Trial expiry logic**: `is_trial_active` must check `trial_started_at + trial_days`, not just comparing to created_at.
5. **Invoice uniqueness**: `unique_together = ('subscription', 'period_start', 'period_end')` prevents duplicate invoices.
6. **Status transitions**: Transition logic (trial → active, active → suspended) happens in management commands + suspenders. Don't allow direct status changes via PATCH.
7. **Rate limiting scope**: Rate limit by IP for registration (public endpoint), not by user (user doesn't exist yet).

---

## Files Modified/Created

**Modified**:
- `backend/tenants/models.py` — add 3 models
- `backend/tenants/admin.py` — register plans, subscriptions, invoices in Django admin
- `backend/config/settings.py` — add billing config (TRIAL_DAYS, etc.)
- `backend/tenants/tests.py` — add 50+ tests

**New**:
- `backend/tenants/serializers.py` — Create/Read serializers for plans, subscriptions, invoices
- `backend/tenants/views.py` — ViewSets and admin endpoints
- `backend/tenants/urls.py` — wire /api/billing/* endpoints
- `backend/tenants/management/commands/check_overdue_subscriptions.py`
- `backend/tenants/management/commands/generate_invoices.py`
- `docs/modules/billing.md` — full documentation

---

## Delivery Checklist

[ ] All models implemented + migrations created  
[ ] All endpoints implemented + tested  
[ ] Management commands working + cron-ready  
[ ] 50+ tests passing  
[ ] Security review passed  
[ ] Documentation complete  
[ ] No console errors on fresh `docker compose up`  
