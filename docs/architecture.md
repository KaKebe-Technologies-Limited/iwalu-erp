# System Architecture

**System**: Nexus ERP
**Company**: Kakebe Technologies, Lira, Uganda
**Purpose**: Multi-tenant ERP for fuel stations and related businesses

---

## Overview

Nexus ERP is a multi-tenant system where each business (tenant) gets its own isolated database schema. A single deployment serves multiple businesses — each with their own outlets, products, sales data, and staff — while sharing the authentication and tenant management infrastructure.

The system is designed around the reality that a fuel station business often operates multiple business types at one location: a fuel station, a cafe, a small supermarket, and potentially a boutique or bridal shop. Rather than separate systems for each, Nexus ERP handles all of them under one tenant with different outlet types and product categories.

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Backend API | Django 5.0 + Django REST Framework | REST API, business logic, ORM |
| Database | PostgreSQL 16 | Data storage with schema-based multi-tenancy |
| Cache | Redis 7 | Caching via django-redis |
| Frontend | Next.js 14 + TypeScript | Web application |
| UI Components | shadcn/ui + Tailwind CSS | Component library + styling |
| State | Zustand (auth) + TanStack Query (API data) | Client-side state management |
| Containerization | Docker + docker-compose | Development and deployment |

---

## Multi-Tenancy

**Approach**: Schema-based isolation via `django-tenants`.

Each tenant (business) gets its own PostgreSQL schema. Tables in the `public` schema are shared across all tenants. Tables in tenant schemas are completely isolated.

### Public Schema (Shared)
- `users.User` — all user accounts
- `tenants.Client` — tenant registry
- `tenants.Domain` — domain-to-tenant mapping
- `allauth` tables — social login accounts/tokens
- Django system tables (auth, sessions, admin, etc.)

### Tenant Schemas (Isolated)
- `outlets.Outlet` — business locations
- `products.Category` — product categories
- `products.Product` — product catalog + stock
- `sales.Discount` — discount definitions
- `sales.Shift` — cashier shifts
- `sales.Sale` — transactions
- `sales.SaleItem` — line items
- `sales.Payment` — payment records

### How Requests Route to Tenants

1. Request arrives at `demo.localhost:8000`
2. `TenantMainMiddleware` looks up the domain in `tenants.Domain`
3. Middleware sets the PostgreSQL `search_path` to that tenant's schema
4. All ORM queries for the rest of the request hit the tenant's tables
5. Shared models (User) always query the `public` schema

### Cross-Schema Limitation

User records live in `public`, but sales/shifts need to reference users. PostgreSQL can't enforce foreign keys across schemas, so tenant-scoped models use `IntegerField(user_id)` instead of `ForeignKey(User)`. The application layer handles the relationship.

---

## Authentication Flow

```
Client                          Backend
  |                                |
  |-- POST /api/auth/login/ ----->|  (email + password)
  |<---- { access, refresh } -----|
  |                                |
  |-- GET /api/users/ ----------->|  (Authorization: Bearer {access})
  |<---- { count, results } ------|
  |                                |
  |-- (access expires) ---------->|
  |<---- 401 --------------------|
  |                                |
  |-- POST /api/auth/refresh/ --->|  (refresh token)
  |<---- { access } -------------|
```

- Access tokens: 1 hour
- Refresh tokens: 7 days
- Social login (Google/Apple) follows the same pattern but the initial token comes from the OAuth provider

---

## Module Dependency Graph

```
tenants (shared)
    |
users (shared)
    |
outlets (tenant)
    |
products (tenant)
    |
sales (tenant) -- depends on --> outlets, products
```

Detailed module documentation is in `docs/modules/`:
- [Auth & Users](modules/auth-users.md)
- [Outlets](modules/outlets.md)
- [Products & Categories](modules/products.md)
- [POS & Sales](modules/pos-sales.md)

---

## API Design

- **Format**: REST with JSON request/response bodies
- **Pagination**: All list endpoints return `{ count, next, previous, results }` (20 items/page)
- **Filtering**: `django-filter` for field-based filtering, `SearchFilter` for text search, `OrderingFilter` for sorting
- **Authentication**: JWT Bearer tokens on all non-public endpoints
- **Documentation**: Auto-generated OpenAPI 3.0 schema via `drf-spectacular`
  - Swagger UI: `/api/docs/`
  - ReDoc: `/api/redoc/`
  - Raw schema: `/api/schema/`

---

## Deployment

Development uses `docker-compose` with four services:

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| backend | Custom (Python 3.12) | 8000 | Django API |
| frontend | Custom (Node 18) | 3000 | Next.js app |
| db | postgres:16 | 5432 | PostgreSQL |
| redis | redis:7-alpine | 6379 | Cache |

Code changes sync via Docker volumes (no rebuild needed for code changes). Only `requirements.txt` or `package.json` changes require a rebuild.

### Tenant Provisioning

```bash
docker-compose exec backend python manage.py create_tenant "Business Name" "domain.localhost"
```

This creates the PostgreSQL schema and runs all tenant-app migrations automatically.
