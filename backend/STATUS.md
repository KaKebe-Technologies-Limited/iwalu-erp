# Backend Status

**Last Updated**: February 27, 2026
**Phase**: 2 — Authentication & User Management

## Implemented

### Apps
- **api** — Routing hub, health check (`GET /api/health/`)
- **users** — Custom User model, JWT auth, user CRUD ViewSet
- **tenants** — Multi-tenancy models (Client + Domain), not yet wired to user flows

### Endpoints
```
GET     /api/health/            → Health check (DB + Redis)
POST    /api/auth/login/        → JWT login (email + password)
POST    /api/auth/refresh/      → Refresh access token
GET     /api/auth/me/           → Current user (requires auth)
GET     /api/users/             → List users
POST    /api/users/             → Create user
GET     /api/users/{id}/        → Retrieve user
PUT/PATCH /api/users/{id}/      → Update user
DELETE  /api/users/{id}/        → Delete user
```

### Infrastructure
- Docker: backend, db (PostgreSQL 16), redis, frontend
- JWT config: 1hr access, 7-day refresh
- CORS: localhost:3000
- Redis caching configured

## TODO (Phase 2 Completion)
- [ ] Custom permission classes (role-based: admin-only, manager+admin, etc.)
- [ ] `POST /api/users/{id}/deactivate/` — deactivate user (admin only)
- [ ] `POST /api/users/{id}/activate/` — activate user (admin only)
- [ ] Search filtering on user list (`SearchFilter` on name/email)
- [ ] Ordering filter on user list (`OrderingFilter`)
- [ ] Pagination config in `REST_FRAMEWORK` settings
- [ ] Register User model in `admin.py`
- [ ] Tests: auth flow (login, refresh, me, invalid creds)
- [ ] Tests: user CRUD (create, list, retrieve, update, permissions)
- [ ] Standardised error response format

## Upcoming (Phase 3 — POS & Sales)
- [ ] Product model (name, sku, price, category, stock)
- [ ] Product CRUD endpoints
- [ ] Sales/Transaction model
- [ ] Checkout endpoint
- [ ] Receipt generation
- [ ] Offline sales queue support

## Known Gaps
- `admin.py` files are empty across all apps
- No custom permission classes exist yet — everything uses default `IsAuthenticated`
- No API documentation (Swagger/OpenAPI)
- No logging configuration
- Tenants app has models but no management commands or onboarding flow
