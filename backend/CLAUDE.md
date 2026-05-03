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

## Phase 8 Learnings (Café, Projects, Manufacturing)

### DRF Router & URL Ordering
When registering multiple ViewSets with a single DefaultRouter, **router registration order matters**:
- **Problem**: Registering with `r''` (empty pattern) for ProjectViewSet first caused it to catch ALL requests, including those meant for child routes like `/projects/expenses/`.
- **Solution**: Register more specific routes (tasks, expenses, time-entries) BEFORE the empty root pattern.
- **Pattern**: `router.register(r'specific', ...); router.register(r'', root_vs)` ensures specific routes are matched first.

### Permission Operator Syntax
Combine DRF permission classes with `|` operator **on the class, not instances**:
```python
# ❌ Wrong: Cannot use | on instances
return [IsAdminOrManager() | IsAccountant()]

# ✅ Correct: Use | on classes, then instantiate
return [(IsAdminOrManager | IsAccountant)()]
```

### Decimal Handling in Serializers
`sum()` returns `int(0)` when the iterable is empty, not `Decimal`. Always initialize Decimal explicitly:
```python
# ❌ Wrong: sum() with empty list returns int
total = sum(item.cost for item in empty_list)
total.quantize(Decimal('0.01'))  # AttributeError: 'int' has no attribute 'quantize'

# ✅ Correct: Initialize as Decimal, accumulate in loop
total = Decimal('0')
for item in items:
    total += item.cost
return total.quantize(Decimal('0.01'))
```

### Atomic Operations with F() Expressions
Use F() and transaction.atomic() for race-condition-safe updates:
```python
# Update project.actual_cost without fetching, preventing lost updates
with transaction.atomic():
    Project.objects.filter(pk=expense.project_id).update(
        actual_cost=F('actual_cost') + expense.amount
    )
    # For deletes, use Greatest() to prevent negative values
    Project.objects.filter(pk=pk).update(
        actual_cost=Greatest(F('actual_cost') - amount, Decimal('0'))
    )
```

### ViewSet Endpoint Validation
When updates affect parent objects, validate child-to-parent relationships:
```python
# In serializer.validate(), check that updated child still points to the correct parent
def validate_project(self, value):
    if self.instance and value.id != self.instance.project_id:
        raise ValidationError("Cannot reassign to a different project during update.")
    return value
```

### Management Command Multi-Tenancy
Wrap command logic with tenant_context to iterate over all tenant schemas:
```python
from django_tenants.utils import get_tenant_model, tenant_context

def handle(self, *args, **options):
    for tenant in get_tenant_model().objects.all():
        with tenant_context(tenant):
            # Command logic runs against this tenant's schema
            Product.objects.all().update(...)
```

## Completed Modules (Phase 8)
- **Café & Bakery** — Menu, recipes, ingredient-level BOM, costing, dine-in/takeaway orders. ✅
- **Project Management** — Projects, tasks, budgets, time tracking, profitability reports. ✅
- **Manufacturing/BOM** — Raw materials, production orders, WIP, finished goods, unit costing. ✅

## Post-Phase Workflow

### After Code Review Approval
1. Ensure all tests pass: `docker compose exec backend python manage.py test <app>`
2. Run security review: Use `/security-reviewer` agent or `security-review` skill.
3. Commit with co-author: Include `Co-Authored-By:` footer if pair-reviewed.
4. Push to branch: `git push origin <branch>`.
5. Create PR or direct merge based on team decision.
6. Update documentation: Module docs in `docs/modules/`, STATUS.md, CLAUDE.md.
7. Notify frontend team: Post to #dev with module readiness, API endpoints, and integration notes.

### Code Review Checklist (Before PR)
- [ ] All tests pass (100% pass rate, no skipped tests).
- [ ] DRF permission classes correctly configured on all ViewSets.
- [ ] URL routing doesn't have conflicting patterns.
- [ ] Serializers handle edge cases (empty lists, null values, Decimals).
- [ ] Atomic operations use F() expressions and transaction.atomic().
- [ ] Documentation updated for new endpoints and models.
- [ ] No N+1 queries (use select_related, prefetch_related).
- [ ] No hardcoded values; use constants or settings.

## Quality Gates
- **Before pushing**: Run `security-reviewer` agent to audit changes for vulnerabilities (OWASP top 10, Django-specific issues, permission gaps).
- **Before PR**: Ensure all tests pass, documentation is complete, and code follows conventions above.
- **After module completion**: Update STATUS.md, CLAUDE.md, and docs/modules/.

## Standards
Refer to backend standards in @../CLAUDE.md
