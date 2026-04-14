# Nexus ERP - Gemini CLI Configuration

**Project**: Multi-tenant Fuel Station ERP  
**Company**: Kakebe Technologies, Lira, Uganda  
**Stack**: Django 5.0/DRF, PostgreSQL 16, Redis, Next.js 14, TypeScript, Docker

**Current Phase**: Phase 6c - Mobile Money & Card Payments (Backend Complete)
**Status**: ✅ Phases 1-6c Backend Complete | 🚧 Frontend Integration (Phases 5-6) | ⏳ Next: Phase 6d Direct MM API

---

## Project Structure

```
erp/
├── docs/                   # System documentation
├── backend/                # Django REST API (see backend/GEMINI.md)
├── frontend/               # Next.js App (see frontend/GEMINI.md)
├── docker-compose.yml
├── .env                    # Environment variables (DO NOT COMMIT)
├── STATUS.md               # Detailed project progress
└── GEMINI.md               # This file
```

---

## Development Workflow (Gemini CLI)

### 1. Research & Strategy
- Use `grep_search` and `glob` to understand existing patterns.
- Always check `STATUS.md` and `docs/` before starting a new feature.
- Use `run_shell_command` to verify backend state or run tests.

### 2. Implementation
- **Surgical Edits**: Use `replace` for targeted changes.
- **New Files**: Use `write_file` for complete new components or modules.
- **Verification**: Always run tests after changes.

### 3. Docker Commands
```bash
# General
docker compose up -d           # Start all in background
docker compose logs -f backend # View logs
docker compose down            # Stop all

# Backend specific
docker compose exec backend python manage.py migrate_schemas
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py test
docker compose exec backend python manage.py shell

# Frontend specific (from root)
# Note: pnpm is used in frontend
```

---

## Technical Standards

### Backend (Django/DRF)
- **Multi-tenancy**: Schema-based isolation via `django-tenants`.
- **API**: DRF with JWT authentication.
- **Naming**: Snake_case for Python, consistent with established modules.
- **Documentation**: Update `docs/modules/` for every new backend feature.

### Frontend (Next.js)
- **Styling**: Tailwind CSS + shadcn/ui.
- **State**: TanStack Query for server state, Zustand for client state.
- **Patterns**: Server components by default, Client components for interactivity.

---

## Project Context (claude-mem)
- **Service**: Reachable at `http://localhost:37777`.
- **Usage**: Query `/api/context/recent` for session history.

---

**Last Updated**: April 2026
**Current Task**: Finalizing Phase 6c (Mobile Money) naming and priority.
