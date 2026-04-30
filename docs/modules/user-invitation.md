# User Invitation

**App**: `users`  
**Type**: Shared (public schema)  
**Phase**: 7a

---

## Overview

Tenant admins and managers invite staff by email. The invitee receives a time-limited link to set up their account. No admin password-sharing required.

---

## Flow

```
1. Admin  →  POST /api/users/invite/          { email, role }
             Backend creates UserInvitation record
             Backend sends invitation email with accept link

2. Invitee opens email, clicks link
   Frontend shows accept-invite form

3. Invitee  →  POST /api/users/accept-invite/ { token, first_name, last_name, username, password }
               Backend creates User account, marks invitation accepted
               Returns JWT tokens → frontend logs user in
```

The accept-invite call **must** be made from the tenant's subdomain (`schema.nexuserp.com`). The backend verifies the invitation token's `tenant_schema` matches the current connection schema.

---

## Endpoints

### Send Invitation

```
POST /api/users/invite/
Authorization: Bearer <admin or manager token>
Content-Type: application/json
```

**Request**

| Field | Type | Notes |
|-------|------|-------|
| email | email | Required |
| role  | string | Required. One of: `manager`, `cashier`, `attendant`, `accountant`. Cannot be `admin`. |

**Response (201 Created)**

```json
{
  "id": 1,
  "email": "jane@acmefuels.com",
  "role": "cashier",
  "is_pending": true,
  "accepted_at": null,
  "expires_at": "2026-04-25T10:00:00Z",
  "created_at": "2026-04-23T10:00:00Z"
}
```

Returns 200 (not 201) if a pending invitation for the same email already exists in this tenant — it reissues the invite with a fresh token and 48-hour expiry.

**Errors**

| Status | Reason |
|--------|--------|
| 400 | Email already has an active user account |
| 400 | Role is `admin` (forbidden via invite) |
| 401 | Not authenticated |
| 403 | Role is cashier, attendant, or accountant |

---

### Accept Invitation

```
POST /api/users/accept-invite/
(public — no authentication required)
Content-Type: application/json
```

Must be called from the tenant's subdomain.

**Request**

| Field | Type | Notes |
|-------|------|-------|
| token | UUID | From the invitation email link |
| first_name | string | Required |
| last_name | string | Required |
| username | string | Required, must be unique |
| password | string | Required, min 8 characters |
| phone_number | string | Optional |

**Response (201 Created)**

```json
{
  "user": {
    "id": 42,
    "email": "jane@acmefuels.com",
    "username": "janed",
    "role": "cashier",
    "is_active": true
  },
  "access": "eyJ...",
  "refresh": "eyJ..."
}
```

**Errors**

| Status | Reason |
|--------|--------|
| 400 | Invalid or missing token |
| 400 | Invitation expired |
| 400 | Invitation already used |
| 400 | Email already has an account |
| 400 | Wrong tenant subdomain |

---

### List Invitations

```
GET /api/users/invitations/
Authorization: Bearer <admin or manager token>
```

Returns all invitations for the current tenant (pending, accepted, and expired).

**Response (200 OK)**

```json
[
  {
    "id": 1,
    "email": "jane@acmefuels.com",
    "role": "cashier",
    "is_pending": true,
    "accepted_at": null,
    "expires_at": "2026-04-25T10:00:00Z",
    "created_at": "2026-04-23T10:00:00Z"
  }
]
```

---

## Model: UserInvitation

Stored in the public schema (`users` is a shared app).

| Field | Type | Notes |
|-------|------|-------|
| email | EmailField | Invitee's email |
| role | CharField | Pre-assigned role |
| tenant_schema | CharField | Schema name of the issuing tenant |
| invited_by_id | IntegerField | PK of the inviting user |
| token | UUIDField | Unique, single-use |
| expires_at | DateTimeField | 48 hours from creation |
| accepted_at | DateTimeField | Set on acceptance, null until then |

`unique_together = ('email', 'tenant_schema')` — one active invite per email per tenant. Re-inviting resets the token and expiry.

---

## Email Backend

Invitation emails are sent via Django's `send_mail`, using the `EMAIL_BACKEND` setting:

- **Development** (default): `django.core.mail.backends.console.EmailBackend` — prints to stdout, no actual mail sent.
- **Production**: Set `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend` and configure `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`.

See `.env.example` for the full list of required variables.

---

## Tests

`users/tests.py` → `UserInvitationTests`

- Admin can send invitation
- Manager can send invitation
- Cashier cannot invite (403)
- Unauthenticated cannot invite (401)
- Cannot invite with admin role (400)
- Cannot invite existing user (400)
- Accept valid invite creates user + returns JWT
- Accept expired invite returns 400
- Accept already-used invite returns 400
- Accept invalid token returns 400
- Accept from wrong tenant schema returns 400
- List invitations requires admin/manager

---

## Curl Examples

```bash
# Send an invitation (from tenant subdomain)
TOKEN="<admin JWT>"
curl -X POST http://acmefuels.localhost:8000/api/users/invite/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"email": "jane@acmefuels.com", "role": "cashier"}'

# Accept an invitation (from tenant subdomain)
curl -X POST http://acmefuels.localhost:8000/api/users/accept-invite/ \
  -H "Content-Type: application/json" \
  -d '{
    "token": "<uuid from email>",
    "first_name": "Jane",
    "last_name": "Doe",
    "username": "janedoe",
    "password": "securepass99"
  }'

# List invitations
curl -H "Authorization: Bearer $TOKEN" \
  http://acmefuels.localhost:8000/api/users/invitations/
```
