# ERP System - Claude Code Configuration

**Project**: Multi-tenant Fuel Station ERP  
**Company**: Kakebe Technologies, Lira, Uganda  
**Team**: Backend (Django/PostgreSQL) + Frontend (Next.js)  
**Stack**: Django 5.0/DRF, PostgreSQL 16, Redis, Next.js 14, TypeScript, Docker

**Current Phase**: Phase 7 Backend Complete — Frontend Integration Pending
**Status**: ✅ Phases 1–7 Backend | 🚧 Frontend Integration (Phases 5–7) | ⏳ Next: Café/Bakery, Projects, Manufacturing

---

## Project Structure

```
erp/
├── docs/                   # System documentation
│   ├── architecture.md    # System overview, multi-tenancy, tech stack
│   └── modules/           # Per-module documentation
│       ├── auth-users.md
│       ├── outlets.md
│       ├── products.md
│       └── pos-sales.md
├── backend/                # Django REST API
│   ├── config/            # Settings, URLs
│   ├── users/             # User management, auth, social login, invitations
│   ├── outlets/           # Outlet management
│   ├── products/          # Product catalog, categories, stock
│   ├── sales/             # POS checkout, shifts, discounts, payments
│   ├── tenants/           # Multi-tenancy, subscription billing (Phase 7b)
│   ├── inventory/         # Suppliers, POs, stock transfers, audit log
│   ├── finance/           # Chart of accounts, journal entries, cash requisitions
│   ├── hr/                # Employees, leave, attendance, payroll
│   ├── fuel/              # Fuel pumps, tanks, reconciliation
│   ├── approvals/         # Multi-level approval workflows (Phase 7c)
│   ├── assets/            # Fixed asset tracking & depreciation (Phase 7d)
│   ├── fiscalization/     # EFRIS/URA tax integration
│   ├── notifications/     # In-app, email, SMS
│   ├── payments/          # MTN MoMo, Airtel, Pesapal
│   ├── system_config/     # Tenant-level settings
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/              # Next.js App
│   ├── app/
│   │   ├── login/        # Public
│   │   └── (dashboard)/  # Protected layout group
│   │       └── dashboard/
│   ├── components/
│   │   ├── layout/       # Sidebar, Topbar
│   │   ├── ui/           # shadcn/ui
│   │   └── [feature]/    # Feature components
│   ├── lib/
│   │   ├── api.ts        # API client
│   │   ├── store/        # Zustand stores
│   │   └── hooks/        # TanStack Query hooks
│   └── Dockerfile
├── docker-compose.yml
├── .env                   # NOT in Git
├── .env.example           # Template (in Git)
└── Claude.md             # This file
```

---

## Daily Workflow

**Morning**
```bash
git pull origin main
docker compose up
# Check #dev channel, review Miro board
```

**During Development**
- Work on Miro tasks
- Commit frequently: `feat: add user search endpoint`
- Push when testable
- Tag teammate if blocked

**End of Day**
```bash
git push
# Update Miro status
# Post in #dev: "Built X, stuck on Y, tomorrow Z"
docker compose down  # optional
```

### Git Workflow
- `main` - stable only
- `backend-feature` / `frontend-feature` - work branches
- Small changes → merge to main
- Large features → PR + quick review

**Commit Format**: `type: description`  
Types: `feat`, `fix`, `refactor`, `docs`, `test`

---

## Docker Commands

```bash
# Daily
docker compose up              # Start all
docker compose up -d           # Background
docker compose logs -f backend # View logs
docker compose ps              # Check status
docker compose down            # Stop all

# After dependency changes
docker compose build backend
docker compose build frontend

# Django commands
docker compose exec backend python manage.py migrate_schemas  # NOT migrate (routes shared/tenant apps correctly)
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py createsuperuser
docker compose exec backend python manage.py test
docker compose exec backend python manage.py shell

# Tenant management
docker compose exec backend python manage.py create_tenant \
  --schema_name demo --name "Demo Business" \
  --domain-domain "localhost" --domain-is_primary True

# Database access
docker compose exec db psql -U nexus_user -d nexus_db

# Nuclear option (deletes DB)
docker compose down -v
```

---

## Backend Standards (Django)

### Model Template
```python
class MyModel(models.Model):
    # Required fields first
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Always include timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
```

### ViewSet Template
```python
class MyViewSet(viewsets.ModelViewSet):
    queryset = MyModel.objects.all()
    serializer_class = MySerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return MyCreateSerializer
        return MySerializer
    
    @action(detail=True, methods=['post'])
    def custom_action(self, request, pk=None):
        obj = self.get_object()
        return Response({'status': 'success'})
```

### API Response Format
```python
# List (paginated)
{"count": 100, "next": "...", "previous": null, "results": [...]}

# Single object
{"id": 1, "name": "...", "created_at": "2026-02-12T10:00:00Z"}

# Error
{"error": "Clear message", "detail": "Context"}
```

### Testing
```python
from rest_framework.test import APITestCase

class UserAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='test@x.com', password='pass')
        self.client.force_authenticate(user=self.user)
    
    def test_list_users(self):
        response = self.client.get('/api/users/')
        self.assertEqual(response.status_code, 200)
```

---

## Frontend Standards (Next.js)

### Component Patterns

**Server Component (default)**
```typescript
// Static content, layouts
export default function UsersPage() {
  return <div><h1>Users</h1><UsersList /></div>;
}
```

**Client Component (interactive)**
```typescript
'use client';
import { useState } from 'react';

export function UsersList() {
  const [search, setSearch] = useState('');
  // interactive logic
}
```

### API Hooks (TanStack Query)
```typescript
// lib/hooks/useUsers.ts
export function useUsers(search = '') {
  return useQuery({
    queryKey: ['users', search],
    queryFn: () => apiClient(`/users/?search=${search}`),
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data) => apiClient('/users/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  });
}
```

### TypeScript
```typescript
interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: 'admin' | 'manager' | 'cashier' | 'attendant' | 'accountant';
  is_active: boolean;
  created_at: string;
}

interface UserTableProps {
  users: User[];
  onEdit: (user: User) => void;
}

export function UserTable({ users, onEdit }: UserTableProps) {
  // ...
}
```

### State Management
- **API data**: TanStack Query (caching, refetching)
- **Auth**: Zustand with localStorage persistence
- **UI state**: React useState
- **Forms**: react-hook-form

### Styling
- Tailwind utility classes only (no custom CSS)
- shadcn/ui for components
- Mobile-first: design for 375px, scale up

---

## API Reference

### Documentation
```
GET    /api/docs/                    → Swagger UI (interactive)
GET    /api/redoc/                   → ReDoc (readable)
GET    /api/schema/                  → OpenAPI 3.0 schema (JSON/YAML)
```

### Authentication
```
POST   /api/auth/login/              → { access, refresh }
POST   /api/auth/refresh/            → { access }
GET    /api/auth/me/                 → User object (requires auth)
POST   /api/auth/register/           → Self-registration
POST   /api/auth/social/google/      → Google OAuth → { access, refresh, user }
POST   /api/auth/social/apple/       → Apple OAuth → { access, refresh, user }
```

### Users
```
GET    /api/users/                    → List (paginated, searchable)
POST   /api/users/                    → Create (admin/manager)
GET    /api/users/{id}/               → Retrieve
PATCH  /api/users/{id}/               → Update (admin/manager)
POST   /api/users/{id}/deactivate/   → Deactivate (admin only)
POST   /api/users/{id}/activate/     → Activate (admin only)
```

### Outlets
```
CRUD   /api/outlets/                  → Outlet management (write: admin/manager)
```

### Products & Categories
```
CRUD   /api/categories/               → Category management (write: admin/manager)
CRUD   /api/products/                  → Product catalog (write: admin/manager)
GET    /api/products/low_stock/        → Low stock products
POST   /api/products/{id}/adjust_stock/ → Stock adjustment (admin/manager)
```

### Shifts
```
GET    /api/shifts/                    → List shifts
POST   /api/shifts/open/               → Open shift (cashier+)
POST   /api/shifts/{id}/close/         → Close shift
GET    /api/shifts/my_current/         → Current user's open shift
```

### Sales & Checkout
```
POST   /api/checkout/                  → Process sale (requires open shift)
GET    /api/sales/                     → Sale history (paginated)
GET    /api/sales/{id}/                → Sale detail with items + payments
POST   /api/sales/{id}/void/           → Void sale (admin/manager)
GET    /api/sales/{id}/receipt/        → Receipt data
```

### Discounts
```
CRUD   /api/discounts/                 → Discount management (write: admin/manager)
```

### Authentication Flow
1. Login → receive `{ access, refresh }`
2. Store in Zustand (localStorage)
3. All requests: `Authorization: Bearer {access}`
4. On 401 → refresh token or redirect to login

**CORS**: Backend allows `http://localhost:3000`

---

## Module Implementation Pattern

Every new feature follows this workflow:

**Backend**
1. `python manage.py startapp module_name`
2. Define models → serializers → ViewSets → permissions
3. Wire URLs, run migrations
4. Write tests, test with curl

**Frontend**
1. Create route: `app/(dashboard)/dashboard/module/page.tsx`
2. Create hooks: `lib/hooks/useModule.ts`
3. Build components: `components/module/`
4. Add to Sidebar navigation
5. Test in browser

**Integration**
- CRUD from frontend works
- Permissions correct
- Search/filter functional
- Mobile responsive

---

## Common Issues

### Port already in use
```bash
lsof -ti:8000 | xargs kill -9
# Or change port in docker-compose.yml: "8001:8000"
```

### Database connection refused
```bash
docker compose ps          # Check DB running
docker compose restart db
# Ensure settings.py has HOST='db' not 'localhost'
```

### CORS errors
- Check `django-cors-headers` installed
- Verify `CORS_ALLOWED_ORIGINS = ["http://localhost:3000"]`
- Confirm `corsheaders.middleware.CorsMiddleware` in MIDDLEWARE

### Token expired
- Access tokens: 1 hour (configurable)
- Handle 401 by refreshing or redirecting to login

### Changes not showing
```bash
docker compose build backend  # After dependency changes
# Code changes sync via volumes automatically
```

---

## Performance

**Backend**
- Use `select_related()` / `prefetch_related()` to avoid N+1
- Add indexes on frequently queried fields
- Enable query logging in dev
- Use Redis for caching

**Frontend**
- TanStack Query handles caching
- Lazy load heavy components
- Debounce search inputs
- Paginate large lists

---

## Security

**Backend**
- Never commit `.env`
- Environment variables for secrets
- Validate all inputs
- Permission classes on ViewSets
- `DEBUG=False` in production

**Frontend**
- Validate forms (but don't trust it)
- Sanitize user inputs before display
- Handle 401 gracefully
- Never log sensitive data

---

## Working with Claude Code

### Prompting
**Good**: "Create DRF ViewSet for Products with fields: name, sku, price. Add search by name/sku. Follow backend standards from Claude.md"

**Bad**: "make me a product thing"

### File References
Use exact paths: `backend/users/views.py`, `frontend/app/(dashboard)/dashboard/users/page.tsx`

### Code Review
"Review this for Django best practices, security (SQL injection/XSS), N+1 queries, and type safety"

---

## Team Communication

**Shared Claude Account**
- Post in #dev before starting Claude Code session
- Keep sessions under 30 minutes when possible
- Share snippets if blocked

**Code Conflicts**
- Pull before starting work
- Communicate which files you're touching
- Resolve conflicts immediately

**Knowledge Sharing**
- Update this Claude.md with new patterns
- Update Miro board as tasks complete
- EOD message with progress/blockers

---

## Quick Reference

### Settings
- `AUTH_USER_MODEL = 'users.User'`
- JWT access: 1 hour, refresh: 7 days
- Pagination: 20 items/page
- Timestamps: UTC

### File Organization
**Backend**: `app_name/` → `models.py`, `serializers.py`, `views.py`, `urls.py`, `permissions.py`, `tests.py`

**Frontend**: `app/` (routes), `components/` (UI), `lib/` (logic)

### Resources
- Django: https://docs.djangoproject.com/
- DRF: https://www.django-rest-framework.org/
- Next.js: https://nextjs.org/docs
- TanStack Query: https://tanstack.com/query/latest
- shadcn/ui: https://ui.shadcn.com/
- Project Stage: @'Nexus ERP – Full System Proposal.pdf' Only refer to this to see what stage the project is at and what the next step should be.
---

**Last Updated**: April 2026
**Current Phase**: 7 — All backend complete through Phase 7d (Assets)
**Next Phase**: Café & Bakery Management, Project Management, Manufacturing/BOM
