# Backend Development Context

**Role**: Backend Developer (Django/DRF)
**Focus**: API endpoints, database models, authentication, business logic
**Scope**: Work exclusively in `/backend`. A separate engineer handles the frontend.

## Not My Concern
- React components, Next.js pages, frontend state, UI/UX, Tailwind

## Project Structure
```
backend/
├── config/          # settings.py, root urls.py, wsgi/asgi
├── api/             # Routing hub, health check endpoint
├── users/           # User model, auth endpoints, user CRUD, social auth
├── tenants/         # Multi-tenancy (django-tenants, schema-based)
├── outlets/         # Outlet management (fuel_station, cafe, supermarket, etc.)
├── products/        # Category + Product catalog, stock management
├── sales/           # Discounts, shifts, checkout, sale history, payments
├── manage.py
├── requirements.txt
└── Dockerfile
```

## Key Architecture
- **Auth**: JWT via `djangorestframework-simplejwt` (1hr access, 7-day refresh)
- **Social Auth**: Google + Apple via `django-allauth` + `dj-rest-auth`
- **User model**: `users.User` extends `AbstractUser`, email as `USERNAME_FIELD`
- **Roles**: admin, manager, cashier, attendant, accountant
- **Multi-tenancy**: `django-tenants` with PostgreSQL schema isolation
- **Tenant-scoped apps**: outlets, products, sales (in TENANT_APPS)
- **User references in tenant apps**: `IntegerField(user_id)` not ForeignKey (cross-schema FK limitation)
- **Database**: PostgreSQL 16 via `django_tenants.postgresql_backend`
- **Cache**: Redis 7 via `django-redis`
- **Settings**: `python-decouple` for env vars
- **Filtering**: `django-filter` for filtering, search, ordering
- **Pagination**: Global PAGE_SIZE=20, PageNumberPagination

## Permission Classes
- `IsAdmin` — admin only
- `IsAdminOrManager` — admin + manager
- `IsCashierOrAbove` — admin + manager + cashier + attendant (excludes accountant)

## Conventions
- Models: timestamps (`created_at`, `updated_at`), `ordering = ['-created_at']`
- Serializers: separate Create vs Read serializers when password handling needed
- Views: `ModelViewSet` with `get_serializer_class()` for action-based serializer switching
- URLs: `DefaultRouter` for ViewSets, explicit paths for function-based views
- Tests: `TenantTestCase` + `TenantClient` for tenant-scoped apps
- Commit format: `type: description` (feat, fix, refactor, test, docs)

## Quick Commands
```bash
# All commands from project root (where docker-compose.yml lives)
docker-compose exec backend python manage.py makemigrations
docker-compose exec backend python manage.py migrate
docker-compose exec backend python manage.py test
docker-compose exec backend python manage.py createsuperuser
docker-compose exec backend python manage.py shell
docker-compose exec db psql -U nexus_user -d nexus_db
docker-compose logs -f backend
```

## Standards
Refer to backend standards in @../CLAUDE.md
