# Backend Status

**Last Updated**: March 6, 2026
**Phase**: 3 — POS & Sales Module

## Phase 2 (Complete)

### Apps
- **api** — Routing hub, health check (`GET /api/health/`)
- **users** — Custom User model, JWT auth, user CRUD ViewSet, social auth (Google + Apple)
- **tenants** — Multi-tenancy models (Client + Domain)

### Auth Endpoints
```
POST    /api/auth/login/             → JWT login (email + password)
POST    /api/auth/refresh/           → Refresh access token
GET     /api/auth/me/                → Current user (requires auth)
POST    /api/auth/register/          → Self-registration
POST    /api/auth/social/google/     → Google OAuth login
POST    /api/auth/social/apple/      → Apple OAuth login
```

### User Endpoints
```
GET     /api/users/                  → List users (paginated, searchable)
POST    /api/users/                  → Create user (admin/manager)
GET     /api/users/{id}/             → Retrieve user
PATCH   /api/users/{id}/             → Update user (admin/manager)
DELETE  /api/users/{id}/             → Delete user (admin/manager)
POST    /api/users/{id}/deactivate/  → Deactivate (admin only)
POST    /api/users/{id}/activate/    → Activate (admin only)
```

## Phase 3 (Complete)

### New Apps
- **outlets** — Outlet management (fuel_station, cafe, supermarket, boutique, bridal, general)
- **products** — Category + Product catalog with stock management
- **sales** — Discounts, shifts, checkout, sale history, payments

### Outlet Endpoints
```
GET    /api/outlets/                     → List (filter: outlet_type, is_active; search: name, address)
POST   /api/outlets/                     → Create (admin/manager)
GET    /api/outlets/{id}/                → Retrieve
PATCH  /api/outlets/{id}/                → Update (admin/manager)
DELETE /api/outlets/{id}/                → Delete (admin/manager)
```

### Category Endpoints
```
GET    /api/categories/                  → List (filter: business_unit, parent, is_active)
POST   /api/categories/                  → Create (admin/manager)
GET    /api/categories/{id}/             → Retrieve
PATCH  /api/categories/{id}/             → Update (admin/manager)
DELETE /api/categories/{id}/             → Delete (admin/manager)
```

### Product Endpoints
```
GET    /api/products/                    → List (search: name, sku, barcode; filter: category, is_active)
POST   /api/products/                    → Create (admin/manager)
GET    /api/products/{id}/               → Retrieve
PATCH  /api/products/{id}/               → Update (admin/manager)
DELETE /api/products/{id}/               → Delete (admin/manager)
GET    /api/products/low_stock/          → Products at/below reorder level
POST   /api/products/{id}/adjust_stock/  → Manual stock adjustment (admin/manager)
```

### Shift Endpoints
```
GET    /api/shifts/                      → List (filter: outlet, status)
POST   /api/shifts/open/                 → Open shift (cashier+)
POST   /api/shifts/{id}/close/           → Close shift with cash count
GET    /api/shifts/my_current/           → Current user's open shift
```

### Checkout & Sales Endpoints
```
POST   /api/checkout/                    → Process sale (core POS endpoint)
GET    /api/sales/                       → List (search: receipt_number; filter: outlet, status, shift)
GET    /api/sales/{id}/                  → Detail with items + payments
POST   /api/sales/{id}/void/             → Void sale, restore stock (admin/manager)
GET    /api/sales/{id}/receipt/          → Receipt data for printing
```

### Discount Endpoints
```
GET    /api/discounts/                   → List (filter: discount_type, is_active)
POST   /api/discounts/                   → Create (admin/manager)
GET    /api/discounts/{id}/              → Retrieve
PATCH  /api/discounts/{id}/              → Update (admin/manager)
DELETE /api/discounts/{id}/              → Delete (admin/manager)
```

### Infrastructure Updates
- Global pagination (PAGE_SIZE=20) on all list endpoints
- `django-filter` for filtering + search + ordering
- `django-allauth` + `dj-rest-auth` for social login
- Permission classes: IsAdmin, IsAdminOrManager, IsCashierOrAbove
- Admin registrations for all models
- Atomic checkout with `select_for_update()` for race condition prevention
- Receipt number format: `OUT{id}-YYYYMMDD-NNNN`

### Resolved Gaps
- **API documentation**: `drf-spectacular` — Swagger UI at `/api/docs/`, ReDoc at `/api/redoc/`, schema at `/api/schema/`
- **Logging**: Configured console logging (INFO default, DEBUG for sales in dev, configurable via `DJANGO_LOG_LEVEL` and `DB_LOG_LEVEL` env vars)
- **Tenant onboarding**: `python manage.py create_tenant "Business Name" "domain.localhost"` management command + admin registrations for Client/Domain

## Upcoming (Phase 4)
- [ ] Inventory management (stock transfers between outlets)
- [ ] Reporting & analytics endpoints
- [ ] Platform admin endpoints (tenant management)

## Known Gaps
- Social login requires Google/Apple credentials to be configured in .env
