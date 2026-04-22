# Nexus ERP

Multi-tenant, offline-first ERP system for various kinds of enterprises.

## Setup

### Prerequisites
- Docker installed
- Git

### Installation

1. Clone the repository
```bash
git clone <your-repo-url>
cd Nexus
```

2. Create environment file
```bash
cp .env.example .env
# Edit .env and add your secret key
cp ./frontend/.env.local.example ./frontend/.env.local
# Edit .env.local and add the correct backend API URL

# P.S: If you have python and django installed, you can generate a secret key by running this command, copying the secret key to the .env file:
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

3. Start Docker containers
```bash
docker compose up
```

4. Run migrations (in new terminal)
```bash
docker compose exec backend python manage.py migrate
```

5. Create superuser
```bash
docker compose exec backend python manage.py createsuperuser
```

6. Access the application
- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- Admin: http://localhost:8000/admin

## Development

### Backend (Django)
```bash
# Run migrations
docker compose exec backend python manage.py migrate

# Create new app
docker compose exec backend python manage.py startapp <app_name>

# Access Django shell
docker compose exec backend python manage.py shell
```

### Database
```bash
# Access PostgreSQL
docker compose exec db psql -U nexus_user -d nexus_db
```

### Logs
```bash
docker compose logs backend
docker compose logs -f backend  # Follow logs
```

## Tech Stack
- Backend: Django + Django REST Framework
- Frontend: Next.js 14
- Database: PostgreSQL 16
- Cache: Redis
- Deployment: Docker
