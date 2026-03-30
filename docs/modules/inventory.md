# Inventory Module

**App**: `inventory`
**Schema**: Tenant-isolated (each business has its own inventory data)
**Dependencies**: `outlets` (stock is per-outlet), `products` (items being tracked)

---

## Purpose

The Inventory module manages supplier relationships, purchase orders, inter-outlet stock transfers, per-outlet stock levels, and a complete audit trail of all stock movements. It integrates with the Sales module — checkout deducts stock and creates audit logs, voids restore stock.

---

## Data Model

### Supplier

| Field | Type | Description |
|-------|------|-------------|
| name | CharField(200) | Supplier company name |
| contact_person | CharField(200) | Primary contact name |
| email | EmailField | Contact email |
| phone | CharField(20) | Phone number |
| address | TextField | Physical address |
| is_active | Boolean | Whether supplier is active |

### OutletStock

Per-outlet stock level tracking. Unique per (outlet, product) pair.

| Field | Type | Description |
|-------|------|-------------|
| outlet | FK → Outlet | Which outlet holds the stock |
| product | FK → Product | Which product |
| quantity | Decimal(12,3) | Current quantity (supports litres/kg) |

### PurchaseOrder

| Field | Type | Description |
|-------|------|-------------|
| po_number | CharField(50) | Auto-generated: PO-YYYYMMDD-NNNN |
| supplier | FK → Supplier | Which supplier |
| outlet | FK → Outlet | Receiving outlet |
| ordered_by | IntegerField | User who created the PO |
| status | CharField | `draft` → `submitted` → `partial`/`received` or `cancelled` |
| expected_date | DateField | Expected delivery date |
| total_cost | Decimal(12,2) | Sum of line totals |
| notes | TextField | Optional notes |

### PurchaseOrderItem

| Field | Type | Description |
|-------|------|-------------|
| purchase_order | FK → PurchaseOrder | Parent PO |
| product | FK → Product | Product being ordered |
| quantity_ordered | Decimal(12,3) | Quantity ordered |
| quantity_received | Decimal(12,3) | Quantity received so far |
| unit_cost | Decimal(12,2) | Cost per unit |
| line_total | Decimal(12,2) | qty_ordered × unit_cost |

### StockTransfer

| Field | Type | Description |
|-------|------|-------------|
| transfer_number | CharField(50) | Auto-generated: TRF-YYYYMMDD-NNNN |
| from_outlet | FK → Outlet | Source outlet |
| to_outlet | FK → Outlet | Destination outlet |
| initiated_by | IntegerField | User who created the transfer |
| status | CharField | `pending` → `in_transit` → `completed` or `cancelled` |
| notes | TextField | Optional notes |

### StockTransferItem

| Field | Type | Description |
|-------|------|-------------|
| transfer | FK → StockTransfer | Parent transfer |
| product | FK → Product | Product being transferred |
| quantity | Decimal(12,3) | Quantity to transfer |
| quantity_received | Decimal(12,3) | Quantity actually received |

### StockAuditLog

Immutable audit trail for every stock change.

| Field | Type | Description |
|-------|------|-------------|
| product | FK → Product | Affected product |
| outlet | FK → Outlet | Affected outlet (nullable) |
| movement_type | CharField | `sale`, `void`, `adjustment`, `transfer_out`, `transfer_in`, `purchase` |
| quantity_change | Decimal(12,3) | Signed change (+/-) |
| quantity_before | Decimal(12,3) | Stock level before change |
| quantity_after | Decimal(12,3) | Stock level after change |
| reference_type | CharField | Source entity type (e.g. "Sale", "PurchaseOrder") |
| reference_id | IntegerField | Source entity ID |
| user_id | IntegerField | Who performed the action |
| notes | TextField | Optional context |

---

## API Endpoints

### Suppliers
```
GET    /api/suppliers/              → List (search: name/contact/email, filter: is_active)
POST   /api/suppliers/              → Create (admin/manager)
GET    /api/suppliers/{id}/         → Retrieve
PATCH  /api/suppliers/{id}/         → Update (admin/manager)
DELETE /api/suppliers/{id}/         → Delete (admin/manager)
```

### Outlet Stock
```
GET    /api/outlet-stock/           → List (filter: outlet, product; order: quantity, updated_at)
GET    /api/outlet-stock/low/       → Low stock items (filter: outlet)
```

### Purchase Orders
```
GET    /api/purchase-orders/        → List (search: po_number/supplier; filter: supplier/outlet/status)
POST   /api/purchase-orders/        → Create with items (admin/manager)
GET    /api/purchase-orders/{id}/   → Retrieve with items
PATCH  /api/purchase-orders/{id}/   → Update (draft only, admin/manager)
DELETE /api/purchase-orders/{id}/   → Delete (draft only, admin/manager)
POST   /api/purchase-orders/{id}/submit/  → Move draft → submitted
POST   /api/purchase-orders/{id}/receive/ → Receive items (partial supported)
POST   /api/purchase-orders/{id}/cancel/  → Cancel (not if received)
```

### Stock Transfers
```
GET    /api/stock-transfers/        → List (search: transfer_number; filter: from_outlet/to_outlet/status)
POST   /api/stock-transfers/        → Create with items (admin/manager)
GET    /api/stock-transfers/{id}/   → Retrieve with items
PATCH  /api/stock-transfers/{id}/   → Update (pending only)
DELETE /api/stock-transfers/{id}/   → Delete (pending only)
POST   /api/stock-transfers/{id}/dispatch/ → Dispatch: deducts from source outlet
POST   /api/stock-transfers/{id}/receive/  → Receive: adds to destination outlet
POST   /api/stock-transfers/{id}/cancel/   → Cancel (pending only)
```

### Stock Audit Log
```
GET    /api/stock-audit-log/        → Read-only list (filter: product/outlet/movement_type)
```

---

## Business Logic

### Purchase Order Workflow
1. **Create** (draft) → validates supplier, outlet, all products exist
2. **Submit** → marks as submitted (ready for delivery)
3. **Receive** → partial or full receipt; updates Product.stock_quantity + OutletStock.quantity; creates audit logs
4. Status auto-transitions: `submitted` → `partial` (some items received) → `received` (all fully received)

### Stock Transfer Workflow
1. **Create** (pending) → validates outlets differ, all products exist
2. **Dispatch** → deducts from source outlet's OutletStock; creates `transfer_out` audit logs
3. **Receive** → adds to destination outlet's OutletStock; creates `transfer_in` audit logs
4. All operations are atomic (wrapped in `transaction.atomic()`)

---

## Frontend Integration

### Hooks (in `frontend/src/lib/hooks/`)
- `useSuppliers.ts` — CRUD operations
- `usePurchaseOrders.ts` — CRUD + submit/receive/cancel
- `useStockTransfers.ts` — CRUD + dispatch/receive/cancel
- `useOutletStock.ts` — Read + low stock
- `useStockAuditLog.ts` — Read with filters

### Page
- `app/dashboard/inventory/page.tsx` — Products table, stock movements, categories, suppliers (wired to real API)

---

## Test Coverage

46+ test cases covering:
- Supplier CRUD and permissions
- PO creation, submission, partial/full receipt, cancellation
- Stock transfer dispatch/receive workflows
- Audit log creation and filtering
- Checkout → inventory sync (sales deduct stock)
- Void → stock restoration
