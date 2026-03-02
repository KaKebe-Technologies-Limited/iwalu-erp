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
├── users/           # User model, auth endpoints, user CRUD
├── tenants/         # Multi-tenancy (django-tenants, schema-based)
├── manage.py
├── requirements.txt
└── Dockerfile
```

## Key Architecture
- **Auth**: JWT via `djangorestframework-simplejwt` (1hr access, 7-day refresh)
- **User model**: `users.User` extends `AbstractUser`, email as `USERNAME_FIELD`
- **Roles**: admin, manager, cashier, attendant, accountant
- **Multi-tenancy**: `django-tenants` with PostgreSQL schema isolation
- **Database**: PostgreSQL 16 via `django_tenants.postgresql_backend`
- **Cache**: Redis 7 via `django-redis`
- **Settings**: `python-decouple` for env vars

## Conventions
- Models: timestamps (`created_at`, `updated_at`), `ordering = ['-created_at']`
- Serializers: separate Create vs Read serializers when password handling needed
- Views: `ModelViewSet` with `get_serializer_class()` for action-based serializer switching
- URLs: `DefaultRouter` for ViewSets, explicit paths for function-based views
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
