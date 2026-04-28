# SaaS Subscription Billing Module

## Overview

The billing module manages multi-tenant SaaS subscriptions, pricing plans, and automated invoicing. It operates in the shared (`public`) schema.

## Models

### SubscriptionPlan
Defines pricing tiers and limits.
- `price_monthly`: UGX price per month.
- `price_annual`: UGX price per year.
- `max_users`: User seat limit.
- `max_outlets`: Branch limit.
- `features`: JSON list of enabled feature slugs.

### TenantSubscription
Tracks the active plan and billing state for a tenant.
- `status`: trial, active, suspended, cancelled, past_due.
- `billing_cycle`: monthly or annual.
- `next_billing_date`: When the next invoice is generated.

### SubscriptionInvoice
Generated at the start of each billing cycle.
- `status`: pending, paid, overdue, cancelled.
- `due_date`: Usually 14 days after issue.

## Lifecycle

1. **Registration**: New tenants start on a **Trial** (default 14 days).
2. **Billing Cycle**: At `next_billing_date`, an invoice is generated and `next_billing_date` is pushed forward.
3. **Payment**: When an invoice is marked paid, the subscription remains active.
4. **Overdue**: If an invoice is unpaid past the grace period (default 7 days), the tenant is **Suspended**.

## Management Commands

### `generate_invoices`
Run daily. Creates invoices for subscriptions whose `next_billing_date` has arrived.
```bash
python manage.py generate_invoices
```

### `check_overdue_subscriptions`
Run daily. Suspends tenants with overdue invoices past the grace period.
```bash
python manage.py check_overdue_subscriptions
```

## Configuration

Settings in `.env`:
- `TRIAL_DAYS`: Days for free trial (default: 14).
- `INVOICE_DUE_DAYS`: Days to pay invoice (default: 14).
- `PAYMENT_GRACE_PERIOD_DAYS`: Days past due before suspension (default: 7).

## Endpoints

- `GET /api/billing/plans/`: Public list of active plans.
- `GET /api/billing/subscriptions/my-subscription/`: Current tenant subscription.
- `POST /api/billing/subscriptions/my-subscription/change-plan/`: Upgrade/downgrade.
- `GET /api/billing/invoices/`: Tenant's invoice history.
- `POST /api/tenants/resend-verification/`: Resend verification email.
