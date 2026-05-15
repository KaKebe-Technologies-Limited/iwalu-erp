# Mobile API Module

**App**: `mobile_api`  
**Phase**: 9  
**Branch**: `feat-phase-9-mobile-api`  
**Status**: Complete ✅

---

## Overview

The Mobile API enables React Native Android cashier apps to operate in environments with intermittent connectivity. Cashiers log in, download a full offline data bundle at shift start, collect sales offline, then sync the batch before closing their shift.

The module introduces:
- Role-restricted mobile JWTs that embed a `client: mobile` claim
- Two permission classes that gate endpoints by token type
- A shift-start data endpoint (products, stock, discounts, pumps)
- A batch sync endpoint (up to 500 offline transactions, idempotent)
- A shift-close guard that blocks close while unsynced transactions remain
- Hardened sensitive endpoints (finance, HR, assets, users, tenants) that reject mobile tokens

---

## Models

### `MobileSyncLog` (`mobile_api/models.py`)

Audit record written after every batch sync, whether or not any transactions succeeded.

| Field | Type | Notes |
|---|---|---|
| `device_id` | CharField(255) | Android device identifier |
| `shift_id` | IntegerField | Cross-schema ref — no FK |
| `user_id` | IntegerField | Cross-schema ref — no FK |
| `outlet_id` | IntegerField | Cross-schema ref — no FK |
| `transaction_count` | PositiveIntegerField | Total submitted |
| `success_count` | PositiveIntegerField | Created as Sales |
| `failed_count` | PositiveIntegerField | Rejected |
| `synced_at` | DateTimeField | Auto set on create |
| `ip_address` | GenericIPAddressField | REMOTE_ADDR of request |

Index on `(shift_id, synced_at)` for shift-based audit queries.

### `Sale` additions (`sales/models.py`)

Two fields added to the existing `Sale` model:

| Field | Type | Notes |
|---|---|---|
| `client_uuid` | UUIDField | Unique, indexed. Null for web POS sales |
| `source` | CharField(10) | `'pos'` (default) or `'mobile'` |

---

## Authentication — `mobile_api/auth.py`

### `POST /api/mobile/auth/login/`

```json
{ "email": "cashier@station.ug", "password": "secret" }
```

- Restricted to `cashier` and `attendant` roles — any other role returns `400`
- Returns standard SimpleJWT `access` + `refresh` tokens
- Access token payload includes extra claims: `"client": "mobile"`, `"role": "cashier"`
- Rate limited to **5 requests/minute** per IP (`MobileLoginThrottle`)

### `POST /api/mobile/auth/refresh/`

Standard SimpleJWT refresh. The `client: mobile` claim propagates automatically to the new access token. Rate limited via `UserRateThrottle`.

---

## Permissions — `mobile_api/permissions.py`

Both classes inspect `request.auth.payload` (SimpleJWT `AccessToken`).

| Class | Allows | Use on |
|---|---|---|
| `IsMobileClient` | Tokens where `payload['client'] == 'mobile'` | Shift-start, sync endpoints |
| `IsNotMobileClient` | Tokens where `payload['client'] != 'mobile'` (includes unauthenticated, handled upstream by `IsAuthenticated`) | Finance, HR, assets, users, tenants |

Web POS tokens carry no `client` claim, so `payload.get('client')` returns `None` — they pass `IsNotMobileClient` automatically.

---

## Endpoints

### `GET /api/mobile/shift-start-data/?outlet_id=<id>`

**Auth**: Mobile JWT + cashier-or-above  
**Requires**: An open shift for the requesting user at the given outlet (prevents cross-outlet data enumeration)

Returns the complete offline bundle:

```json
{
  "outlet": { "id": 1, "name": "Lira Central", "outlet_type": "fuel_station" },
  "products": [
    {
      "id": 12, "name": "Petrol", "sku": "PTL-001", "barcode": null,
      "category_id": 3, "category_name": "Fuel",
      "selling_price": "5000.00", "tax_rate": "18.00",
      "track_stock": true, "unit": "litre",
      "outlet_stock": "487.500"
    }
  ],
  "categories": [{ "id": 3, "name": "Fuel", "business_unit": "fuel_station" }],
  "discounts": [{ "id": 5, "name": "Fleet 10%", "discount_type": "percentage", "value": "10.00", "valid_until": null }],
  "pumps": [{ "id": 1, "pump_number": 1, "name": "Pump A", "product_id": 12, "status": "active" }],
  "generated_at": "2026-05-13T08:00:00.000000+00:00"
}
```

- Products: all active products with current outlet stock levels (single query, no N+1)
- Discounts: active only, with `valid_until` in the future or null
- Pumps: active only, filtered to the requested outlet

---

### `POST /api/mobile/sync/`

**Auth**: Mobile JWT + cashier-or-above  
**Throttle**: 10 requests/minute per authenticated user

```json
{
  "device_id": "android-abc123",
  "shift_id": 7,
  "transactions": [
    {
      "client_uuid": "550e8400-e29b-41d4-a716-446655440000",
      "created_at": "2026-05-13T09:15:00Z",
      "items": [
        { "product_id": 12, "quantity": "10.000", "unit_price": "5000.00", "discount_id": null }
      ],
      "payments": [
        { "payment_method": "cash", "amount": "59000.00", "reference": "" }
      ],
      "notes": ""
    }
  ]
}
```

**Validation**:
- `device_id`: regex `[a-zA-Z0-9_-]{8,64}`
- `transactions`: max 500 per request
- `unit_price`: min `0.01`; `quantity`: min `0.001`; `notes`: max 500 chars
- Shift must be open and owned by the authenticated user

**Per-transaction processing** (each in its own `atomic()` savepoint):
1. Deduplication — if `client_uuid` already exists in `Sale`, returns `status: duplicate`
2. Product validation — must be active
3. Stock check + deduction — `select_for_update()` locks product and `OutletStock` rows
4. Sale, SaleItem, Payment creation
5. Stock audit log entry
6. Fiscalization submission (non-blocking; failures logged, sale not aborted)

**Response**:

```json
{
  "processed": 1,
  "results": [
    {
      "client_uuid": "550e8400-e29b-41d4-a716-446655440000",
      "status": "synced",
      "sale_id": 204,
      "receipt_number": "S001-2026-0204",
      "message": null
    }
  ]
}
```

`status` values: `synced` | `duplicate` | `failed`

A `MobileSyncLog` record is always written, even if all transactions failed.

---

### `POST /api/shifts/{id}/close/` (updated)

The existing close-shift endpoint now accepts `pending_mobile_transactions`:

```json
{ "closing_cash": "85000", "pending_mobile_transactions": 2 }
```

If `pending_mobile_transactions > 0`, returns `400`:

```json
{ "error": "Sync 2 pending transaction(s) before closing shift." }
```

If the field is omitted it defaults to `0` (shift closes normally). This is an advisory guard — the server trusts the client-reported count.

---

## Sensitive Endpoint Hardening

`IsNotMobileClient` is applied to all ViewSets and `@api_view` functions in:

| File | Scope |
|---|---|
| `finance/views.py` | AccountViewSet, FiscalPeriodViewSet, JournalEntryViewSet, CashRequisitionViewSet, and all `@api_view` report functions |
| `hr/views.py` | All 8 ViewSets + `terminate`, `approve`, `reject` `@action` overrides |
| `assets/views.py` | AssetCategoryViewSet, AssetViewSet (including `schedule` action) |
| `users/views.py` | UserViewSet only — auth endpoints (`/auth/login/`, `/auth/refresh/`, `/auth/me/`) are excluded |
| `tenants/views.py` | SubscriptionPlanViewSet, TenantSubscriptionViewSet, SubscriptionInvoiceViewSet — public registration endpoints excluded |

Not applied to: `products`, `sales`, `fuel`, `notifications`, `system_config` (mobile needs these).

---

## Migrations

| Migration | App | Contents |
|---|---|---|
| `0002_sale_client_uuid_source.py` | `sales` | Adds `client_uuid` (UUID, unique, indexed) and `source` (CharField choices) to `Sale` |
| `0001_mobile_sync_log.py` | `mobile_api` | Creates `MobileSyncLog` table with composite index on `(shift_id, synced_at)` |

Run with `migrate_schemas` (not `migrate`).

---

## Tests

42 tests across 5 groups — all passing.

| Group | Count | Coverage |
|---|---|---|
| `MobileLoginTests` | 6 | Role restrictions, wrong password, inactive user |
| `ShiftStartDataTests` | 10 | Missing/invalid outlet, stock map, expired discounts, inactive pumps, outlet ownership, JWT type |
| `BatchSyncTests` | 16 | Happy path, deduplication, stock failure, partial batch, batch limit, shift ownership, closed shift, payment shortfall, missing product, inactive product, sync log creation/counts, shift not found, auth |
| `ShiftCloseTests` | 4 | Zero pending, nonzero pending (blocked), missing field default, log presence |
| `IsNotMobileClientTests` | 6 | Finance, HR, assets, users — mobile rejected / web accepted |

All tests use `TenantTestCase` + `TenantClient`. Throttle cache is cleared in `setUp` so rapid test runs don't hit rate limits.

---

## Security Notes

- JWT claim `client: mobile` is cryptographically bound to the server's `SECRET_KEY` — cannot be forged without it
- `select_for_update()` on product and `OutletStock` rows prevents TOCTOU stock races under concurrent syncs
- Internal Python exceptions are logged server-side; only `ValueError` messages (business logic) are returned to the client
- Outlet ownership check on shift-start-data prevents cross-outlet product/stock enumeration
- Known open items (pre-existing, not introduced by Phase 9): `SECRET_KEY` has a hardcoded fallback default; `ALLOWED_HOSTS = ['*']` — both should be fixed in the production environment configuration pass

---

*Last updated: 2026-05-16*
