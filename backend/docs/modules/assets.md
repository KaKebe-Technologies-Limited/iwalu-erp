# Assets Module

The Assets module provides fixed asset tracking for fuel stations and office equipment.

## Features
- **Asset Registration**: Categorization, cost, acquisition, location, assignment.
- **Assignment Lifecycle**: Tracks staff assignment history.
- **Maintenance Logs**: Service, repair, and downtime history.
- **Depreciation**: Straight-line and Reducing Balance methods.
- **Disposal**: Sale, scrap, or write-off tracking with gain/loss.

## API Endpoints

### Categories
- `GET /api/assets/categories/`
- `POST /api/assets/categories/` (Admin only)

### Assets
- `GET /api/assets/`
- `POST /api/assets/`
- `GET /api/assets/{id}/`
- `PATCH /api/assets/{id}/`
- `POST /api/assets/{id}/assign/`
- `POST /api/assets/{id}/log-maintenance/`
- `POST /api/assets/{id}/dispose/`

### Reports
- `GET /api/assets/depreciation/schedule/`

## Management Commands
- `calculate_monthly_depreciation`: Run at month-end. Use `--journal` to auto-create journal entries in the finance module.
