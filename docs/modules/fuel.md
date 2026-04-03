# Fuel Station Management Module

**App**: `fuel`  
**Type**: Tenant-scoped  
**Dependencies**: outlets, products, sales (Shift), inventory (Supplier, OutletStock, StockAuditLog)

---

## Overview

Manages fuel station operations: pumps, storage tanks, fuel deliveries, meter readings, and daily reconciliation with variance detection.

---

## Models

### Pump
Physical fuel dispenser at an outlet.

| Field | Type | Notes |
|-------|------|-------|
| outlet | FK → Outlet | PROTECT |
| product | FK → Product | Fuel type this pump dispenses |
| pump_number | PositiveInteger | Unique per outlet |
| name | CharField(100) | e.g. "Pump 1 - Petrol" |
| status | CharField | active, inactive, maintenance |

**Constraints**: `unique_together('outlet', 'pump_number')`

### Tank
Underground fuel storage tank.

| Field | Type | Notes |
|-------|------|-------|
| outlet | FK → Outlet | PROTECT |
| product | FK → Product | Fuel type stored |
| name | CharField(100) | e.g. "Underground Tank 1" |
| capacity | Decimal(12,3) | Max volume in litres |
| current_level | Decimal(12,3) | Updated by readings/deliveries |
| reorder_level | Decimal(12,3) | Low-level alert threshold |
| is_active | Boolean | Default True |

**Properties**: `fill_percentage`, `is_low`

### TankReading
Periodic tank level measurement.

| Field | Type | Notes |
|-------|------|-------|
| tank | FK → Tank | CASCADE |
| reading_level | Decimal(12,3) | Litres |
| reading_type | CharField | manual, automatic, delivery, reconciliation |
| recorded_by | IntegerField | user_id |
| reading_at | DateTime | When reading was taken |

### PumpReading
Meter reading per pump per shift.

| Field | Type | Notes |
|-------|------|-------|
| pump | FK → Pump | CASCADE |
| shift | FK → Shift | PROTECT |
| opening_reading | Decimal(12,3) | Meter at shift start |
| closing_reading | Decimal(12,3) | Meter at shift end (nullable) |
| recorded_by | IntegerField | user_id |

**Constraints**: `unique_together('pump', 'shift')`  
**Property**: `volume_dispensed` (closing - opening)

### FuelDelivery
Fuel received into a tank.

| Field | Type | Notes |
|-------|------|-------|
| tank | FK → Tank | PROTECT |
| supplier | FK → Supplier | PROTECT |
| delivery_date | DateTime | |
| volume_ordered | Decimal(12,3) | Optional (detect short deliveries) |
| volume_received | Decimal(12,3) | Actual volume |
| unit_cost | Decimal(12,2) | Per litre |
| total_cost | Decimal(12,2) | Computed |
| tank_level_before | Decimal(12,3) | Snapshot |
| tank_level_after | Decimal(12,3) | Snapshot |
| received_by | IntegerField | user_id |

### FuelReconciliation
Daily comparison of expected vs actual tank levels.

| Field | Type | Notes |
|-------|------|-------|
| date | DateField | |
| outlet | FK → Outlet | PROTECT |
| tank | FK → Tank | PROTECT |
| opening_stock | Decimal(12,3) | |
| closing_stock | Decimal(12,3) | Actual |
| total_received | Decimal(12,3) | Deliveries for the day |
| total_dispensed | Decimal(12,3) | From pump readings |
| expected_closing | Decimal(12,3) | opening + received - dispensed |
| variance | Decimal(12,3) | closing - expected |
| variance_percentage | Decimal(5,2) | |
| variance_type | CharField | gain, loss, within_tolerance |
| status | CharField | draft, confirmed |
| reconciled_by | IntegerField | user_id |

**Constraints**: `unique_together('date', 'tank')`  
**Tolerance**: 0.5% (configurable in services.py)

---

## API Endpoints

### Pumps (`/api/fuel/pumps/`)
| Method | Endpoint | Permission | Description |
|--------|----------|------------|-------------|
| GET | `/` | Authenticated | List pumps (filter: outlet, product, status) |
| POST | `/` | Admin/Manager | Create pump |
| GET | `/{id}/` | Authenticated | Retrieve pump |
| PATCH | `/{id}/` | Admin/Manager | Update pump |
| DELETE | `/{id}/` | Admin/Manager | Delete pump |
| POST | `/{id}/activate/` | Admin/Manager | Activate (from inactive/maintenance) |
| POST | `/{id}/deactivate/` | Admin/Manager | Deactivate (from active) |
| POST | `/{id}/set-maintenance/` | Admin/Manager | Set maintenance (from active) |

### Tanks (`/api/fuel/tanks/`)
| Method | Endpoint | Permission | Description |
|--------|----------|------------|-------------|
| GET | `/` | Authenticated | List tanks (filter: outlet, product, is_active) |
| POST | `/` | Admin/Manager | Create tank |
| GET | `/{id}/` | Authenticated | Retrieve tank |
| PATCH | `/{id}/` | Admin/Manager | Update tank |
| DELETE | `/{id}/` | Admin/Manager | Delete tank |
| POST | `/{id}/record-reading/` | Cashier+ | Record a tank reading |
| GET | `/{id}/readings/` | Authenticated | List readings (filter: date_from, date_to) |
| GET | `/low-levels/` | Authenticated | Tanks below reorder level |

### Pump Readings (`/api/fuel/pump-readings/`)
| Method | Endpoint | Permission | Description |
|--------|----------|------------|-------------|
| GET | `/` | Authenticated | List readings (filter: pump, shift, outlet) |
| POST | `/` | Cashier+ | Open a reading (pump_id, shift_id, opening_reading) |
| GET | `/{id}/` | Authenticated | Retrieve reading |
| POST | `/{id}/close/` | Cashier+ | Close reading (closing_reading) |
| PATCH | `/{id}/` | Admin/Manager | Manual correction |
| DELETE | `/{id}/` | Admin/Manager | Delete reading |

### Fuel Deliveries (`/api/fuel/deliveries/`)
| Method | Endpoint | Permission | Description |
|--------|----------|------------|-------------|
| GET | `/` | Authenticated | List deliveries (filter: tank, supplier, outlet) |
| POST | `/` | Admin/Manager | Record delivery (auto-updates tank + inventory) |
| GET | `/{id}/` | Authenticated | Retrieve delivery |
| PATCH | `/{id}/` | Admin/Manager | Update delivery |
| DELETE | `/{id}/` | Admin/Manager | Delete delivery |

### Reconciliation (`/api/fuel/reconciliations/`)
| Method | Endpoint | Permission | Description |
|--------|----------|------------|-------------|
| GET | `/` | Authenticated | List reconciliations (filter: outlet, tank, variance_type, status) |
| POST | `/calculate/` | Admin/Manager | Auto-calculate reconciliation for a tank+date |
| POST | `/{id}/confirm/` | Admin/Manager | Confirm draft reconciliation |
| GET | `/variance-alerts/` | Authenticated | Non-tolerable variances (filter: outlet, date range) |

### Reports
| Method | Endpoint | Permission | Description |
|--------|----------|------------|-------------|
| GET | `/api/fuel/reports/daily-pump/` | Admin/Manager | Per-pump dispensing for a date |
| GET | `/api/fuel/reports/variance/` | Admin/Manager | Variance summary over date range |
| GET | `/api/fuel/reports/tank-levels/` | Authenticated | Current tank levels |

---

## Business Logic (services.py)

### record_tank_reading
Creates reading, updates tank.current_level. Validates 0 <= level <= capacity.

### process_fuel_delivery
Atomic operation:
1. Validates volume won't exceed tank capacity
2. Creates FuelDelivery with before/after snapshots
3. Updates tank.current_level
4. Creates post-delivery TankReading
5. Syncs with inventory (Product.stock_quantity, OutletStock, StockAuditLog)
6. Attempts journal entry creation (fail-safe)

### close_pump_reading
Validates closing >= opening. Sets closing_reading on the PumpReading.

### calculate_reconciliation
1. Determines opening stock (previous reconciliation or earliest reading)
2. Determines closing stock (provided or latest reading)
3. Sums deliveries for the day
4. Sums pump readings for the day
5. Calculates expected vs actual, variance, and variance type
6. Creates/updates reconciliation record (idempotent per tank+date)

### Variance Tolerance
Default: 0.5%. Variances within tolerance are classified as `within_tolerance`.
Above tolerance: `gain` (positive) or `loss` (negative).

---

## Integration Points

| Module | Integration |
|--------|-------------|
| **inventory** | Deliveries sync with OutletStock, Product.stock_quantity, and StockAuditLog |
| **sales** | PumpReading links to Shift for per-shift tracking |
| **finance** | Deliveries create journal entries (debit Fuel Inventory, credit AP) |
| **products** | Pumps and tanks link to fuel products |
| **outlets** | All models scoped to outlet |

---

## Reconciliation Workflow

1. **Start of day**: Attendant records opening tank readings (manual dip)
2. **During shift**: Pump readings opened/closed per shift
3. **Deliveries**: Manager records fuel received → auto-updates tank level
4. **End of day**: Attendant records closing tank readings
5. **Reconciliation**: Manager runs calculate → system computes variance
6. **Review**: Manager confirms or investigates variance alerts
