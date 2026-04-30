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
├── inventory/       # Suppliers, outlet stock, purchase orders, transfers, audit log
├── reports/         # Sales/inventory/shift analytics, dashboard summary
├── finance/         # Chart of accounts, journal entries, financial reports
├── hr/              # Employees, departments, leave, attendance, payroll
├── notifications/   # In-app notifications, preferences, templates
├── system_config/   # Tenant settings, approval thresholds, audit settings
├── approvals/       # Multi-level approval workflows for critical transactions
├── assets/          # Fixed asset tracking, depreciation, assignment, disposal (Phase 7d)
├── fiscalization/   # EFRIS/URA tax integration (MockProvider + WeafProvider)
├── payments/        # MTN MoMo, Airtel Money, Pesapal (collections + disbursements)
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
- **Tenant-scoped apps**: outlets, products, sales, inventory, reports, finance, hr, fuel, notifications, system_config (in TENANT_APPS)
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
- `IsAccountant` — accountant only
- `IsAccountantOrAbove` — admin + manager + accountant

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
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate_schemas  # NOT migrate (routes shared/tenant apps correctly)
docker compose exec backend python manage.py test
docker compose exec backend python manage.py createsuperuser
docker compose exec backend python manage.py shell
docker compose exec db psql -U nexus_user -d nexus_db
docker compose logs -f backend
```

## Currency (UGX)
- UGX has no fractional subdivision — use `DecimalField(decimal_places=0)` or `str(amount)` for JSON storage
- Never use `float()` for currency; `str(Decimal)` is lossless when serializing to JSON
- "Cents" terminology is wrong for UGX — avoid it in code, comments, and field names

## Remaining Modules (Not Yet Built)
- **Café & Bakery** — Menu, recipes, ingredient-level BOM, costing, dine-in/takeaway orders
- **Project Management** — Projects, tasks, budgets, time tracking, profitability reports
- **Manufacturing/BOM** — Raw materials, production orders, WIP, finished goods, unit costing

## Quality Gates
- **Before pushing or completing a feature**: Run the `security-reviewer` agent to audit changes for vulnerabilities (OWASP top 10, Django-specific issues, permission gaps)
- **After adding a new module**: Create documentation in `docs/modules/` and update STATUS.md

## Standards
Refer to backend standards in @../CLAUDE.md
