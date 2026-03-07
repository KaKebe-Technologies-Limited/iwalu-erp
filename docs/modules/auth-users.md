# Authentication & User Management Module

**App**: `users`
**Schema**: Shared (public schema — users exist across all tenants)
**Dependencies**: None (all other modules reference users)

---

## Purpose

Handles user accounts, authentication, and role-based access control. Supports email/password login via JWT tokens and social login via Google and Apple OAuth. The user model is in the shared (public) schema because it's used across all tenants.

---

## Data Model

### User

Extends Django's `AbstractUser` with email as the primary identifier.

| Field | Type | Description |
|-------|------|-------------|
| email | EmailField, unique | Primary login identifier |
| username | CharField | Required but secondary to email |
| first_name | CharField | User's first name |
| last_name | CharField | User's last name |
| phone_number | CharField(20) | Optional phone number |
| role | CharField(20) | One of: `admin`, `manager`, `cashier`, `attendant`, `accountant` |
| is_active | Boolean | Account active/deactivated status |
| created_at | DateTime | Account creation timestamp |
| updated_at | DateTime | Last update timestamp |

**Cross-schema note**: Because the User model lives in the public schema and tenant-scoped apps (outlets, products, sales) live in isolated tenant schemas, tenant models reference users via `IntegerField(user_id)` rather than a ForeignKey. This is a django-tenants limitation with cross-schema foreign keys.

---

## Roles & Permissions

| Role | Description | POS Access | Management Access |
|------|-------------|------------|-------------------|
| admin | Full system access | Yes | Full CRUD on all resources |
| manager | Location management | Yes | CRUD on outlets, products, discounts, void sales |
| cashier | Primary POS operator | Yes | Read-only on management resources |
| attendant | Fuel pump / floor staff | Yes | Read-only on management resources |
| accountant | Financial oversight | No (view only) | Read-only on all resources |

### Permission Classes (`users/permissions.py`)

- **IsAdmin** — admin role only
- **IsAdminOrManager** — admin or manager
- **IsCashierOrAbove** — admin, manager, cashier, attendant (excludes accountant)

---

## Authentication

### JWT Tokens

- **Access token**: 1 hour lifetime
- **Refresh token**: 7 day lifetime
- All authenticated requests require `Authorization: Bearer {access_token}` header
- On 401, client should attempt token refresh before redirecting to login

### Social Login (Google & Apple)

Uses `django-allauth` + `dj-rest-auth` to bridge OAuth providers to JWT.

**Flow**:
1. Frontend obtains OAuth token from Google/Apple via their JS SDKs
2. Frontend sends token to backend: `POST /api/auth/social/google/`
3. Backend verifies token with the provider, creates or links a User account
4. Backend returns JWT tokens (same format as email/password login)

**Configuration**: OAuth credentials are stored in environment variables (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, etc.) and referenced in `config/settings.py`.

---

## API Endpoints

### Authentication
| Method | Endpoint | Permission | Description |
|--------|----------|------------|-------------|
| POST | `/api/auth/login/` | Public | Login with email + password, returns `{ access, refresh }` |
| POST | `/api/auth/refresh/` | Public | Refresh access token using refresh token |
| GET | `/api/auth/me/` | Authenticated | Get current user's profile |
| POST | `/api/auth/register/` | Public | Self-registration |
| POST | `/api/auth/social/google/` | Public | Google OAuth login |
| POST | `/api/auth/social/apple/` | Public | Apple OAuth login |

### User Management
| Method | Endpoint | Permission | Description |
|--------|----------|------------|-------------|
| GET | `/api/users/` | Authenticated | List users (paginated, searchable by name/email) |
| POST | `/api/users/` | Admin/Manager | Create user |
| GET | `/api/users/{id}/` | Authenticated | Retrieve user |
| PATCH | `/api/users/{id}/` | Admin/Manager | Update user |
| DELETE | `/api/users/{id}/` | Admin/Manager | Delete user |
| POST | `/api/users/{id}/deactivate/` | Admin | Deactivate user account |
| POST | `/api/users/{id}/activate/` | Admin | Reactivate user account |

---

## Key Files

| File | Purpose |
|------|---------|
| `users/models.py` | Custom User model (extends AbstractUser) |
| `users/serializers.py` | User serializers (separate create vs read for password handling) |
| `users/views.py` | UserViewSet + auth endpoints (me, register) |
| `users/permissions.py` | IsAdmin, IsAdminOrManager, IsCashierOrAbove |
| `users/social_auth.py` | GoogleLogin, AppleLogin views (dj-rest-auth bridge) |
| `users/urls.py` | URL routing for auth + user CRUD |
| `users/admin.py` | Django admin registration |

---

## Referenced By

- **sales.Shift** — `user_id` (IntegerField) references the cashier
- **sales.Sale** — `cashier_id` (IntegerField) references who processed the sale
- All ViewSets use permission classes from `users/permissions.py`
