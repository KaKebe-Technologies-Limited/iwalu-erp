# Manufacturing & Bill of Materials (BOM)

The Manufacturing module handles production processes where raw materials are converted into finished goods. This is particularly used for bakery operations, café food production, or any manufacturing process within the ERP.

## Key Concepts

### 1. Bill of Materials (BOM)
A "recipe" for a finished product. It defines:
- **Finished Product**: The item being produced.
- **Output Quantity**: How many units one batch produces.
- **Items**: List of raw materials (ingredients) needed, including waste factors.
- **Unit Cost**: Automatically computed based on ingredient costs.

### 2. Production Orders
A specific instruction to produce a quantity of a product using a BOM.
- **Lifecycle**: `Draft` → `In Progress` → `Completed` (or `Cancelled`).
- **Atomic Stock Conversion**: On completion, raw materials are deducted and finished goods are added in a single atomic transaction.

### 3. Work in Progress (WIP)
Informational snapshots recorded during long-running production processes to track estimated completion percentage and value consumed.

## Data Models

### BillOfMaterials
A recipe defining how to produce a finished product.
| Field | Type | Description |
|-------|------|-------------|
| finished_product | OneToOne(Product) | The product this BOM produces |
| output_quantity | Decimal | Units produced per batch |
| output_unit | CharField | Unit of measurement (kg, liters, units, etc.) |
| unit_cost | Decimal | Cached cost per output unit; updated by `update_bom_costs` command |
| is_active | Boolean | Inactive BOMs cannot start new orders |
| created_at, updated_at | DateTime | Timestamps |

### BillOfMaterialsItem
A row in the BOM, linking a raw material to the recipe.
| Field | Type | Description |
|-------|------|-------------|
| bom | ForeignKey(BillOfMaterials) | Parent recipe |
| raw_material | ForeignKey(Product) | Ingredient |
| quantity_required | Decimal | Amount needed |
| unit | CharField | Unit of measurement |
| waste_factor_pct | Decimal | Waste percentage (e.g., 5.0 for 5% waste) |
| effective_quantity | Computed | `quantity_required * (1 + waste_factor_pct / 100)` |

### ProductionOrder
A specific instruction to manufacture a quantity of a product using a BOM.
| Field | Type | Description |
|-------|------|-------------|
| order_number | String | Unique ID (MFG-YYYYMMDD-XXXX) |
| bom | ForeignKey(BillOfMaterials) | Recipe to follow |
| status | Choices | draft, in_progress, completed, cancelled |
| quantity_to_produce | Decimal | Planned output quantity |
| outlet | ForeignKey(Outlet) | Where production happens |
| created_at, updated_at | DateTime | Timestamps |

### ProductionOrderItem
Captures cost snapshot at production time.
| Field | Type | Description |
|-------|------|-------------|
| order | ForeignKey(ProductionOrder) | Parent order |
| raw_material | ForeignKey(Product) | Material used |
| quantity_used | Decimal | Actual quantity deducted |
| cost_per_unit | Decimal | Cost at time of production (frozen) |
| total_cost | Decimal | `quantity_used * cost_per_unit` |

## API Endpoints

### BOMs
- `GET /api/manufacturing/boms/` - List BOMs
- `POST /api/manufacturing/boms/` - Create BOM + items
- `GET /api/manufacturing/boms/{id}/cost/` - Detailed cost breakdown

### Orders
- `GET /api/manufacturing/orders/` - List orders
- `POST /api/manufacturing/orders/` - Create order
- `POST /api/manufacturing/orders/{id}/start/` - Mark as in progress
- `POST /api/manufacturing/orders/{id}/complete/` - Finalize and adjust stock
- `POST /api/manufacturing/orders/{id}/wip/` - Log WIP snapshot

## Validation & Constraints

### BOM Validation
- **Circular References**: Detects if a product is both a finished_product and appears as a raw_material (e.g., BOM A produces X, BOM B uses X as ingredient, X cannot reference back to A).
- **Duplicate Items**: Cannot add the same raw material twice in a single BOM.
- **Inactive Check**: Cannot create a ProductionOrder from an inactive BOM.

### Order Lifecycle
- **Draft → In Progress**: Can only start if all raw materials are in stock.
- **In Progress → Completed**: Performs atomic stock conversion (deduct raw materials, add finished goods) in a transaction.
- **Completed/Cancelled → No Changes**: Cannot update or delete completed/cancelled orders.

### Stock Movement Logic (The `complete` action)

1. **Shortage Check**: Verifies ALL ingredients are in stock at the production outlet.
   - Includes waste factors: effective_quantity = quantity_required * (1 + waste_factor_pct / 100).
2. **Locking**: Uses `select_for_update()` on `OutletStock` rows to prevent race conditions during concurrent orders.
3. **Atomic Deduction**: Within a single transaction:
   - Deducts each raw material from `OutletStock`.
   - Adds finished goods quantity to `OutletStock`.
   - Creates `ProductionOrderItem` records with cost snapshot.
4. **Audit Log**: Creates `StockAuditLog` entries for every movement with `reference_type='manufacturing_order'`.
5. **Cost Capture**: Freezes raw material costs at the time of production in `ProductionOrderItem` records (prevents cost changes from affecting past orders).

## Cost Calculation

### Unit Cost Propagation
- **BOM's `unit_cost`**: Sum of `(effective_quantity * raw_material.cost_price)` for all items, divided by output_quantity.
- **When Updated**: 
  - When a BOM item is added/modified (inline via serializer validation).
  - Periodically via `update_bom_costs` management command.
  - Ensures financial reports reflect current ingredient costs.

### Waste Factor Impact
Waste is built into `effective_quantity` for inventory deduction and cost calculation:
- Example: BOM with 1 kg flour at 5% waste = 1.05 kg deducted from stock and costed.
- Waste is NOT tracked separately; it's embedded in the cost per unit produced.

## Management Commands

### `update_bom_costs`
Recalculates `unit_cost` for all active BOMs based on the current `cost_price` of ingredients in the product catalog. Useful after bulk product cost updates.
```bash
python manage.py update_bom_costs --tenant demo
```
Runs for all tenants unless `--tenant` is specified.

## Permissions
- **Admin/Manager**: Full access to BOMs, orders, and cost reports.
- **Accountant**: Read-only access to cost reports and historical orders.
- **Operators/Attendants**: Can view BOMs and create/manage orders for their outlet.
