# Iwalu ERP

Multi-tenant, offline-first ERP system for fuel stations.

## Setup

### Prerequisites
- Docker Desktop installed
- Git

### Installation

1. Clone the repository
```bash
git clone <your-repo-url>
cd iwalu-erp
```

2. Create environment file
```bash
cp .env.example .env
# Edit .env and add your secret key
```

3. Start Docker containers
```bash
docker-compose up
```

4. Run migrations (in new terminal)
```bash
docker-compose exec backend python manage.py migrate
```

5. Create superuser
```bash
docker-compose exec backend python manage.py createsuperuser
```

6. Access the application
- Backend: http://localhost:8000
- Admin: http://localhost:8000/admin

## Development

### Backend (Django)
```bash
# Run migrations
docker-compose exec backend python manage.py migrate

# Create new app
docker-compose exec backend python manage.py startapp <app_name>

# Access Django shell
docker-compose exec backend python manage.py shell
```

### Database
```bash
# Access PostgreSQL
docker-compose exec db psql -U iwalu_user -d iwalu_db
```

### Logs
```bash
docker-compose logs backend
docker-compose logs -f backend  # Follow logs
```

## Tech Stack
- Backend: Django + Django REST Framework
- Frontend: Next.js 14
- Database: PostgreSQL 16
- Cache: Redis
- Deployment: Docker
