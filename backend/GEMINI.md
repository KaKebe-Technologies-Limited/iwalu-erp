# Backend Development - Gemini CLI Standards

**Focus**: API, Models, Business Logic, Multi-tenancy
**Location**: `/backend`

## Core Mandates
- **Multi-tenancy**: Use `migrate_schemas` for migrations. Never use standard `migrate`.
- **Cross-schema References**: Use `IntegerField(user_id)` instead of `ForeignKey` for references to the `public` schema from `tenant` schemas.
- **Permissions**: Use project-specific classes: `IsAdmin`, `IsAdminOrManager`, `IsCashierOrAbove`, `IsAccountant`.

## Common Commands
```bash
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate_schemas
docker compose exec backend python manage.py test
docker compose exec backend python manage.py shell
```

## Implementation Workflow
1. **Model**: Define in `models.py` with `created_at` and `updated_at`.
2. **Serializer**: Use ModelSerializers, split into Read/Create if necessary.
3. **ViewSet**: Inherit from `viewsets.ModelViewSet`, implement `get_serializer_class`.
4. **URLs**: Register in `urls.py` via `DefaultRouter`.
5. **Tests**: Write `TenantTestCase` to verify logic within a schema.

## API Response Format
- **Paginated List**: `{"count": X, "next": "...", "previous": "...", "results": [...]}`
- **Single Object**: `{"id": 1, ...}`
- **Errors**: `{"error": "Message", "detail": "Context"}`

---

Refer to root `GEMINI.md` for overall project standards.
