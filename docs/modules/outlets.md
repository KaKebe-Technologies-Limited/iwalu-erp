# Outlets Module

**App**: `outlets`
**Schema**: Tenant-isolated (each business manages its own outlets)
**Dependencies**: None (other modules depend on this one)

---

## Purpose

An outlet represents a physical business location — a fuel station, cafe, supermarket, boutique, bridal shop, or general store. Outlets are the organizational unit that ties together shifts, sales, and (in future phases) inventory transfers.

Every sale and every shift belongs to a specific outlet. This allows per-location reporting, stock tracking, and staff assignment.

---

## Data Model

### Outlet

| Field | Type | Description |
|-------|------|-------------|
| name | CharField(200) | Outlet name (e.g. "Lira Main Station") |
| outlet_type | CharField(20) | One of: `fuel_station`, `cafe`, `supermarket`, `boutique`, `bridal`, `general` |
| address | TextField | Physical address (optional) |
| phone | CharField(20) | Contact phone number (optional) |
| is_active | Boolean | Whether the outlet is currently operational |
| created_at | DateTime | Auto-set on creation |
| updated_at | DateTime | Auto-updated on save |

**Design note**: The `outlet_type` field allows a single tenant to operate multiple business types. A fuel station company might also have a cafe and a small supermarket on-site — each is a separate outlet with its own type, shifts, and sales.

---

## API Endpoints

| Method | Endpoint | Permission | Description |
|--------|----------|------------|-------------|
| GET | `/api/outlets/` | Authenticated | List outlets (filter: outlet_type, is_active; search: name, address) |
| POST | `/api/outlets/` | Admin/Manager | Create outlet |
| GET | `/api/outlets/{id}/` | Authenticated | Retrieve outlet |
| PATCH | `/api/outlets/{id}/` | Admin/Manager | Update outlet |
| DELETE | `/api/outlets/{id}/` | Admin/Manager | Delete outlet |

All list responses are paginated (20 items/page). Supports ordering by `name` and `created_at`.

---

## Permissions

| Action | Roles Allowed |
|--------|---------------|
| View outlets | All authenticated users |
| Create/edit/delete outlets | Admin, Manager only |

---

## Key Files

| File | Purpose |
|------|---------|
| `outlets/models.py` | Outlet model |
| `outlets/serializers.py` | OutletSerializer |
| `outlets/views.py` | OutletViewSet with permission-based access |
| `outlets/urls.py` | URL routing |
| `outlets/tests.py` | 6 tests covering CRUD, permissions, filtering, search |
| `outlets/admin.py` | Django admin registration |

---

## Used By

- **sales.Shift** — every shift belongs to an outlet
- **sales.Sale** — every sale is recorded against an outlet
- Future: inventory transfers between outlets
