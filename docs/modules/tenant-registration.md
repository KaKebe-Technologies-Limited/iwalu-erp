# Tenant Registration & Onboarding

**Apps**: `tenants`, `users`  
**Type**: Shared (public schema)  
**Phase**: P1 / 7a

---

## Overview

Enables self-service business onboarding and role-based dashboard access control:

1. **Tenant registration** — public endpoint for businesses to sign up and receive their own isolated schema, admin user, and subdomain
2. **Email verification** — admin clicks a link in the welcome email to activate their account and receive JWT tokens
3. **Staff invitations** — admin invites team members by email (see `docs/modules/user-invitation.md`)
4. **Role permissions endpoint** — returns allowed sidebar sections and fine-grained actions for the current user's role

---

## Tenant Registration Flow

```
1. Business owner fills in registration form on nexuserp.com/register
   POST /api/tenants/register/
   ↓
   - Client (schema) + Domain + admin user created atomically
   - Admin is_active = False (cannot log in yet)
   - TenantEmailVerification token created (24h expiry)
   - Verification email sent to admin_email

2. Admin checks email, clicks "Verify my account"
   Link: https://nexuserp.com/api/tenants/verify-email/?token=<uuid>
   ↓
   - Admin is_active flipped to True
   - Token marked used (single-use)
   - JWT tokens returned + redirect_url to tenant subdomain

3. Frontend redirects to redirect_url (schema.nexuserp.com/dashboard)
   Admin logs in with their credentials
```

---

## Endpoints

### POST /api/tenants/register/

```
POST /api/tenants/register/
Content-Type: application/json
(public, no authentication required)
```

**Request body**

| Field | Type | Validation |
|-------|------|-----------|
| business_name | string | Required, 1–100 chars |
| schema_name | string | Required, 3–30 chars, lowercase letters/digits/hyphens, must start with a letter, not reserved |
| admin_email | email | Required, globally unique |
| admin_username | string | Required, globally unique |
| admin_password | string | Required, min 8 chars |
| admin_first_name | string | Required |
| admin_last_name | string | Required |
| admin_phone | string | Optional |

**Reserved schema names** (rejected): `public`, `www`, `api`, `admin`, `app`, `auth`, `mail`, `ftp`, `blog`, `help`, `support`, `docs`, `status`, `dev`, `staging`, `test`, `tests`, `postgres`, `information_schema`, `pg_catalog`.

**Response (201 Created)**

```json
{
  "tenant": {
    "id": 2,
    "schema_name": "acmefuels",
    "name": "Acme Fuels Ltd",
    "created_on": "2026-04-23"
  },
  "domain": "acmefuels.nexuserp.com",
  "admin_user": {
    "id": 5,
    "email": "owner@acmefuels.com",
    "username": "acmeowner",
    "role": "admin",
    "is_active": false
  },
  "message": "Registration received. A verification email has been sent to owner@acmefuels.com. Click the link to activate your account."
}
```

**Note**: No JWT tokens are returned here. The admin cannot log in until the email is verified.

**What happens atomically**

1. `Client` row created in public schema → triggers `CREATE SCHEMA` + all TENANT_APPS migrations
2. `Domain` row created mapping `{schema_name}.{TENANT_BASE_DOMAIN}` to the tenant
3. Admin `User` created in shared schema (`is_active=False`, `is_staff=False`, `is_superuser=False`)
4. `TenantEmailVerification` token created (24h TTL)
5. Verification email dispatched (non-blocking — if email fails, tenant is still created and error is logged)

---

### GET /api/tenants/verify-email/

```
GET /api/tenants/verify-email/?token=<uuid>
(public, no authentication required)
```

Called when the admin clicks the link in the verification email. This endpoint lives on the main domain (not the tenant subdomain).

**Response (200 OK)**

```json
{
  "access": "eyJ...",
  "refresh": "eyJ...",
  "redirect_url": "https://acmefuels.nexuserp.com/dashboard",
  "tenant": {
    "schema_name": "acmefuels",
    "name": "Acme Fuels Ltd"
  },
  "message": "Email verified. Your account is now active."
}
```

**Errors**

| Status | Reason |
|--------|--------|
| 400 | Token missing, invalid, expired, or already used |
| 500 | Internal error (logged server-side, safe message returned) |

**Token rules**: single-use, 24-hour TTL. If expired, the business must re-register (current limitation — a "resend verification" endpoint can be added later).

---

## Configuration

```bash
# .env
TENANT_BASE_DOMAIN=nexuserp.com          # production
TENANT_SELF_REGISTRATION_ENABLED=True    # False by default (private beta mode)

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your@email.com
EMAIL_HOST_PASSWORD=app-password
DEFAULT_FROM_EMAIL=Nexus ERP <noreply@nexuserp.com>
```

In development, leave `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` — the verification link prints to Docker logs instead of being sent.

---

## Role Permissions Endpoint

```
GET /api/auth/me/permissions/
Authorization: Bearer <token>
```

Returns the dashboard sections and fine-grained actions the current user's role is allowed to access. The frontend uses this to build the sidebar dynamically and to show/hide feature buttons.

**Response (200 OK)**

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

**Role access matrix**

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

**Source of truth**: `backend/users/role_permissions.py`. When updating: (1) update `ROLE_PERMISSIONS`, (2) audit matching ViewSet `permission_classes`, (3) update the table above, (4) notify the frontend developer.

**Important**: the frontend `sections` list is advisory — every ViewSet still enforces its own permissions server-side.

---

## Tests

### Tenant registration (`tenants/tests.py`)

**Validation (fast, no schema creation)**
- Schema name: invalid chars, too short, starts with digit, reserved names all rejected
- Duplicate schema name, email, or username rejected
- Weak password rejected; invalid email rejected; missing fields return full errors
- Schema name normalised to lowercase

**Integration (slow, creates real PG schema)**
- End-to-end: Client + Domain + admin user created; admin is `is_active=False`; no JWT tokens in response

**Disabled state**
- Returns 503 when `TENANT_SELF_REGISTRATION_ENABLED=False`

### Email verification (`tenants/tests.py` → `EmailVerificationTests`)

- Valid token activates user and returns JWT tokens + redirect_url
- Missing token returns 400
- Invalid token returns 400
- Expired token returns 400
- Already-used token returns 400

### Role permissions (`users/tests.py`)

- Unauthenticated → 401
- Admin gets all sections and all actions
- Manager has most sections but no `settings`
- Cashier has POS/shifts/fuel but no accounting
- Accountant has finance/reports but no POS
- Attendant has fuel/POS only

---

## Curl Examples

```bash
# Register a new business (sends verification email)
curl -X POST https://nexuserp.com/api/tenants/register/ \
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

# Verify email (normally triggered by clicking the link in the email)
curl "https://nexuserp.com/api/tenants/verify-email/?token=<uuid>"

# Use the returned access token at the tenant subdomain
TOKEN="<access token from verify-email>"
curl -H "Authorization: Bearer $TOKEN" \
  https://acmefuels.nexuserp.com/api/auth/me/permissions/
```

---

## Known Limitations

- No "resend verification email" endpoint yet — if the token expires, the business must re-register
- No CAPTCHA on the registration endpoint (should add before public launch)
- No subscription/billing integration — all tenants are provisioned free
- `TENANT_BASE_DOMAIN` must be wildcarded at DNS and reverse-proxy level for production
