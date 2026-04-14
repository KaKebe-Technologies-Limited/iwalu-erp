# Tenant Registration & Role Permissions

**Apps**: `tenants`, `users`
**Type**: Shared (public schema)
**Phase**: P1 (post-6b)

---

## Overview

Enables self-service business onboarding and role-based dashboard access control:

1. **Tenant registration** — public endpoint for businesses to sign up and get their own isolated tenant schema, admin user, and subdomain
2. **Role permissions endpoint** — returns allowed sidebar sections and fine-grained actions for the current user's role, used by the frontend to build dynamic menus and route guards

---

## Tenant Self-Registration

### Endpoint

```
POST /api/tenants/register/
Content-Type: application/json
(public, no authentication required)
```

### Request body

| Field | Type | Validation |
|-------|------|-----------|
| business_name | string | Required, 1-100 chars |
| schema_name | string | Required, 3-30 chars, lowercase letters/digits/underscore, must start with a letter, not reserved |
| admin_email | email | Required, must be unique across all users |
| admin_username | string | Required, must be unique |
| admin_password | string | Required, min 8 chars |
| admin_first_name | string | Required |
| admin_last_name | string | Required |
| admin_phone | string | Optional |

**Reserved schema names** (rejected): `public`, `www`, `api`, `admin`, `app`, `auth`, `mail`, `ftp`, `blog`, `help`, `support`, `docs`, `status`, `dev`, `staging`, `test`, `tests`, `postgres`, `information_schema`, `pg_catalog`.

### Response (201 Created)

```json
{
  "tenant": {
    "id": 2,
    "schema_name": "acmefuels",
    "name": "Acme Fuels Ltd",
    "created_on": "2026-04-05"
  },
  "domain": "acmefuels.localhost",
  "login_url": "http://acmefuels.localhost/api/auth/login/",
  "admin_user": {
    "id": 5,
    "email": "owner@acmefuels.com",
    "username": "acmeowner",
    "first_name": "John",
    "last_name": "Doe",
    "role": "admin"
  },
  "access": "eyJ0eXAi...",
  "refresh": "eyJ0eXAi..."
}
```

The returned JWT tokens authenticate the new admin user immediately — no extra login step needed.

### What happens atomically

1. `Client` row created in the public schema → triggers PostgreSQL `CREATE SCHEMA` + runs all TENANT_APPS migrations
2. `Domain` row created mapping `{schema_name}.{TENANT_BASE_DOMAIN}` to the tenant
3. First admin user created in the shared `users_user` table with `role='admin'`

All three happen inside a single `transaction.atomic()` block. If any step fails, everything rolls back.

### Configuration

Set `TENANT_BASE_DOMAIN` in `.env`:

```bash
# Local development
TENANT_BASE_DOMAIN=localhost

# Production
TENANT_BASE_DOMAIN=nexuserp.com
```

This controls the full domain constructed during registration.

### Validation rules

- **Schema name**: 3-30 chars, `^[a-z][a-z0-9_]+$`, lowercase, not reserved, globally unique
- **Email**: valid email format, case-insensitive uniqueness across all users
- **Username**: case-insensitive uniqueness
- **Password**: minimum 8 characters (stronger rules should be added before production)

### Limitations (future work)

- No email verification
- No CAPTCHA / rate limiting (should add before public launch)
- No billing/subscription integration — all tenants are free today
- `TENANT_BASE_DOMAIN` must be wildcarded at the DNS/reverse-proxy level for production use

---

## Role Permissions Endpoint

### Endpoint

```
GET /api/auth/me/permissions/
Authorization: Bearer <token>
```

Returns the dashboard sections and fine-grained actions the current user's role is allowed to access. The frontend uses this to build the sidebar dynamically and to show/hide feature buttons.

### Response (200 OK)

```json
{
  "role": "manager",
  "sections": [
    "dashboard", "pos", "sales", "shifts", "products", "discounts",
    "inventory", "outlets", "employees", "fuel", "accounting",
    "reports", "notifications"
  ],
  "actions": [
    "open_shift", "close_shift", "process_sale", "void_sale",
    "manage_products", "adjust_stock", "manage_discounts",
    "manage_outlets", "manage_employees", "manage_fuel_pumps",
    "manage_fuel_deliveries", "confirm_reconciliation",
    "view_finance", "view_reports",
    "manage_notifications_templates", "manage_system_config"
  ]
}
```

### Role access matrix

| Section | admin | manager | accountant | cashier | attendant |
|---|---|---|---|---|---|
| dashboard | ✓ | ✓ | ✓ | ✓ | ✓ |
| pos | ✓ | ✓ | | ✓ | ✓ |
| sales | ✓ | ✓ | ✓ | ✓ | |
| shifts | ✓ | ✓ | | ✓ | ✓ |
| products | ✓ | ✓ | | ✓ | |
| discounts | ✓ | ✓ | | | |
| inventory | ✓ | ✓ | ✓ | | |
| outlets | ✓ | ✓ | | | |
| employees | ✓ | ✓ | | | |
| fuel | ✓ | ✓ | | ✓ | ✓ |
| accounting | ✓ | ✓ | ✓ | | |
| reports | ✓ | ✓ | ✓ | | |
| notifications | ✓ | ✓ | ✓ | ✓ | ✓ |
| settings | ✓ | | | | |

### Source of truth

The authoritative mapping lives in `backend/users/role_permissions.py`. When updating:

1. Update `ROLE_PERMISSIONS` dict
2. Audit the corresponding ViewSet `permission_classes` to make sure backend enforcement matches
3. Update this table
4. Notify the frontend developer so they update sidebar icons and route guards

**Important**: the frontend returning `sections` is advisory only — every ViewSet still enforces its own permissions. Never trust the frontend to block access on its own.

---

## Tests

### Tenant registration (`tenants/tests.py`)

- Successful registration creates Client + Domain + admin user + JWT tokens
- Schema name is normalized to lowercase
- Invalid characters, too short, starts-with-digit, reserved names all rejected
- Duplicate schema name, email, or username rejected
- Weak password (< 8 chars) rejected
- Invalid email format rejected
- Missing required fields return full field errors
- Public (no auth) access works
- Returned JWT token authenticates the new admin immediately against `/api/auth/me/`

### Role permissions (`users/tests.py`)

- Unauthenticated access returns 401
- Admin gets all sections + all actions including `manage_audit_settings`
- Manager has most sections but no `settings` or `manage_audit_settings`
- Cashier has POS/shifts/fuel but no accounting/outlets
- Accountant has finance/reports but no POS
- Attendant has fuel/POS only

---

## Curl examples

```bash
# Register a new business
curl -X POST http://localhost:8000/api/tenants/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "business_name": "Acme Fuels Ltd",
    "schema_name": "acmefuels",
    "admin_email": "owner@acmefuels.com",
    "admin_username": "acmeowner",
    "admin_password": "securepass123",
    "admin_first_name": "John",
    "admin_last_name": "Doe",
    "admin_phone": "+256700000000"
  }'

# Use the returned access token to check permissions
TOKEN="<access token from above>"
curl -H "Authorization: Bearer $TOKEN" \
  http://acmefuels.localhost:8000/api/auth/me/permissions/
```
