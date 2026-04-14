# System Configuration Module

**App**: `system_config`  
**Type**: Tenant-scoped  
**Phase**: 6b  

---

## Overview

Tenant-level configuration management for business rules, alert thresholds, receipt customisation, and audit trail settings. Includes an approval workflow engine that determines required roles for high-value transactions.

---

## Models

### SystemConfig
Singleton per tenant schema — stores all tenant-wide settings.

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| variance_tolerance_pct | Decimal(5,2) | 0.50 | Acceptable fuel variance % (0-10) |
| low_stock_threshold_pct | Decimal(5,2) | 20.00 | Low stock alert % of reorder level |
| low_fuel_threshold_pct | Decimal(5,2) | 25.00 | Low fuel alert % of capacity |
| business_name | CharField(255) | blank | Tenant business name |
| tax_id | CharField(50) | blank | Tax identification number |
| currency_code | CharField(3) | UGX | ISO 4217 currency code |
| timezone | CharField(50) | Africa/Kampala | IANA timezone |
| date_format | CharField(20) | YYYY-MM-DD | Display date format |
| receipt_header | TextField | blank | Custom receipt header text |
| receipt_footer | TextField | blank | Custom receipt footer text |
| enable_email_notifications | BooleanField | False | Global email toggle |
| enable_sms_notifications | BooleanField | False | Global SMS toggle |

**Singleton enforcement**: `save()` override prevents multiple rows.

### ApprovalThreshold
Defines which transactions require approval and by whom.

| Field | Type | Notes |
|-------|------|-------|
| transaction_type | CharField | purchase_order, stock_transfer, expense, journal_entry, fuel_delivery |
| min_amount | Decimal(15,2) | Lower bound (inclusive) |
| max_amount | Decimal(15,2) | Upper bound (nullable = unlimited) |
| requires_role | CharField | manager or admin |
| is_active | BooleanField | Default True |

**Validation**: max_amount > min_amount when both set.

### AuditSetting
Controls which audit log types are active and their retention.

| Field | Type | Notes |
|-------|------|-------|
| log_type | CharField | login, data_change, deletion, permission_change, export (unique) |
| is_enabled | BooleanField | Default True |
| retention_days | PositiveIntegerField | 7-3650 days, default 90 |

---

## API Endpoints

### System Config (singleton)
```
GET    /api/system-config/                   Retrieve tenant config
PATCH  /api/system-config/1/                 Update config (admin/manager)
POST   /api/system-config/check-approval/    Check if transaction needs approval
```

### Approval Thresholds
```
GET    /api/approval-thresholds/              List (all authenticated)
POST   /api/approval-thresholds/              Create (admin only)
GET    /api/approval-thresholds/{id}/         Retrieve
PATCH  /api/approval-thresholds/{id}/         Update (admin only)
DELETE /api/approval-thresholds/{id}/         Delete (admin only)
```

### Audit Settings
```
GET    /api/audit-settings/         List (admin only)
POST   /api/audit-settings/         Create (admin only)
GET    /api/audit-settings/{id}/    Retrieve (admin only)
PATCH  /api/audit-settings/{id}/    Update (admin only)
DELETE /api/audit-settings/{id}/    Delete (admin only)
```

---

## Permissions

| Action | Required Role |
|--------|--------------|
| View system config | All authenticated |
| Update system config | Admin, Manager |
| Check approval | All authenticated |
| View approval thresholds | All authenticated |
| CRUD approval thresholds | Admin only |
| CRUD audit settings | Admin only |

---

## Service Functions

| Function | Purpose |
|----------|---------|
| `get_system_config()` | Get singleton with caching (5min TTL) |
| `update_system_config()` | Update fields + invalidate cache |
| `get_required_approval_role()` | Determine required role for transaction |
| `check_approval()` | Check if user's role satisfies approval requirement |

---

## Caching

`SystemConfig` is cached with key `system_config` and 5-minute TTL. Cache is invalidated on update via `update_system_config()`.

---

## Integration Points

| Consumer | Usage |
|----------|-------|
| fuel module | `variance_tolerance_pct` for reconciliation tolerance |
| notifications module | `enable_email_notifications`, `enable_sms_notifications` |
| inventory module | `low_stock_threshold_pct` for alert triggers |
| sales module | Receipt header/footer for receipt generation |
| finance/inventory | `check_approval()` for high-value transactions |

---

## Tests

- **Service tests**: Default creation, update, cache invalidation, singleton enforcement
- **Approval tests**: No threshold, match, below min, tiered thresholds, role hierarchy
- **API tests**: GET/PATCH config, permission checks, check-approval endpoint
- **Threshold API**: CRUD + validation (min/max)
- **Audit setting API**: CRUD + permission checks (admin only)
