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
| Field | Type | Description |
|-------|------|-------------|
| finished_product | OneToOne(Product) | The product this BOM produces |
| output_quantity | Decimal | Units produced per batch |
| unit_cost | Decimal | Cached cost per output unit |
| is_active | Boolean | Inactive BOMs cannot start new orders |

### ProductionOrder
| Field | Type | Description |
|-------|------|-------------|
| order_number | String | Unique ID (MFG-YYYYMMDD-XXXX) |
| status | Choices | draft, in_progress, completed, cancelled |
| quantity_to_produce | Decimal | Planned output |
| outlet | ForeignKey(Outlet) | Where production happens |

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

## Stock Movement Logic (The `complete` action)

1. **Shortage Check**: Verifies ALL ingredients are in stock at the production outlet.
2. **Locking**: Uses `select_for_update()` on `OutletStock` rows to prevent race conditions.
3. **Atomic Deduction**: Deducts raw materials and adds finished goods.
4. **Audit Log**: Creates `StockAuditLog` entries for every movement with `reference_type='manufacturing_order'`.
5. **Cost Capture**: Freezes raw material costs at the time of production in `ProductionOrderItem` records.

## Management Commands

### `update_bom_costs`
Recalculates `unit_cost` for all active BOMs based on the current `cost_price` of ingredients in the product catalog.
```bash
python manage.py update_bom_costs
```
