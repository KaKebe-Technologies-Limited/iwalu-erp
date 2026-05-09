# Phase 8c Implementation Plan: Manufacturing & Bill of Materials (BOM)

**Backend only** (tenant-scoped, new `manufacturing` app)
**Estimated scope**: 5 models, 8 endpoints, 1 management command, ~40 tests
**New apps**: `manufacturing` (tenant-scoped)
**Tenant-scoped**: Yes

---

## Overview

Implements the manufacturing module for bakery and production operations:
1. **Bill of Materials (BOM)**: Define raw material recipes for finished goods
2. **Production Orders**: Order to produce N units; locks material requirements
3. **Stock conversion**: Completing an order deducts raw material stock and adds finished product stock — atomically
4. **WIP tracking**: Work-in-progress snapshots for in-flight production
5. **Unit costing**: BOM unit cost auto-computed from ingredient prices
6. **Audit trail**: All stock movements logged to `inventory.StockAuditLog`

Integrates with `products` (both raw materials and finished goods are `Product` objects), `inventory` (OutletStock + StockAuditLog), and `outlets` (production is outlet-scoped).

---

## Models

### `BillOfMaterials` (in `manufacturing/models.py`)

```python
class BillOfMaterials(models.Model):
    """
    Recipe defining which raw materials produce a finished product.
    One BOM per finished product (OneToOneField).
    unit_cost is a cached computed field — refresh via update_bom_costs command.
    """
    finished_product = models.OneToOneField(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='bill_of_materials',
        help_text='The product this BOM produces'
    )
    name = models.CharField(
        max_length=255,
        help_text='e.g., "Standard Bread Loaf BOM v2"'
    )
    version = models.CharField(max_length=20, default='1.0')

    # Output quantity (one full BOM batch produces this many units)
    output_quantity = models.DecimalField(
        max_digits=12, decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
        help_text='Units of finished product produced per BOM batch'
    )
    output_unit = models.CharField(
        max_length=20,
        help_text='Unit of finished product (e.g., loaves, kg, litres)'
    )

    # Cached cost (recomputed by update_bom_costs command)
    unit_cost = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0'),
        help_text='Cost per unit of finished product (total BOM cost / output_quantity)'
    )

    is_active = models.BooleanField(
        default=True,
        help_text='Inactive BOMs cannot be used to create production orders'
    )
    notes = models.TextField(blank=True)
    created_by_id = models.IntegerField(help_text='User ID who created this BOM')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['finished_product__name']
        indexes = [
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.name} → {self.finished_product.name} (v{self.version})"

    def compute_unit_cost(self) -> Decimal:
        """
        Compute cost per output unit from current BOM items and product prices.
        Does not save — call save() or use update_bom_costs command.
        """
        if self.output_quantity == 0:
            return Decimal('0')
        total_batch_cost = sum(
            item.effective_quantity * (item.raw_material.cost_price or Decimal('0'))
            for item in self.items.select_related('raw_material').all()
        )
        return (total_batch_cost / self.output_quantity).quantize(Decimal('0.01'))
```

---

### `BOMItem` (in `manufacturing/models.py`)

```python
class BOMItem(models.Model):
    """
    A single raw material component in a BOM.
    waste_factor_pct adds buffer above the base quantity_required.
    effective_quantity is what actually gets deducted from stock.
    """
    bom = models.ForeignKey(
        BillOfMaterials, on_delete=models.CASCADE, related_name='items'
    )
    raw_material = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        help_text='Raw material product consumed in production'
    )
    quantity_required = models.DecimalField(
        max_digits=12, decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
        help_text='Quantity of raw material needed per BOM batch (before waste)'
    )
    unit = models.CharField(
        max_length=20,
        help_text='Unit of measurement (must match product stock unit)'
    )
    waste_factor_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text='Percentage of additional material to account for waste/shrinkage'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']
        unique_together = ('bom', 'raw_material')

    def __str__(self):
        return f"{self.bom.name} ← {self.effective_quantity} {self.unit} {self.raw_material.name}"

    @property
    def effective_quantity(self) -> Decimal:
        """Actual quantity deducted from stock, including waste buffer."""
        multiplier = Decimal('1') + (self.waste_factor_pct / Decimal('100'))
        return (self.quantity_required * multiplier).quantize(Decimal('0.001'))
```

---

### `ProductionOrder` (in `manufacturing/models.py`)

```python
class ProductionOrder(models.Model):
    """
    An order to produce a quantity of finished goods from a BOM.
    Status lifecycle: draft → in_progress → completed (or cancelled).
    Stock movements occur only on completion.
    """
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    order_number = models.CharField(
        max_length=30, unique=True,
        help_text='Auto-generated: MFG-YYYYMMDD-XXXX'
    )
    bom = models.ForeignKey(
        BillOfMaterials, on_delete=models.PROTECT, related_name='production_orders'
    )

    # Quantities
    quantity_to_produce = models.DecimalField(
        max_digits=12, decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
        help_text='Number of finished product units to produce'
    )
    quantity_produced = models.DecimalField(
        max_digits=12, decimal_places=3, default=Decimal('0'),
        help_text='Actual units produced (set at completion)'
    )

    # Status
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.DRAFT
    )

    # Timeline
    planned_start = models.DateTimeField(null=True, blank=True)
    actual_start = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Outlet where stock will be adjusted
    outlet = models.ForeignKey(
        'outlets.Outlet', on_delete=models.PROTECT,
        help_text='Outlet whose stock is adjusted on completion'
    )

    # Staff (cross-schema safe)
    ordered_by_id = models.IntegerField(help_text='User ID who created the order')

    # Computed at completion
    total_material_cost = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0'),
        help_text='Sum of raw material costs at time of production'
    )

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'outlet']),
            models.Index(fields=['bom']),
        ]

    def __str__(self):
        return f"{self.order_number} — {self.bom.finished_product.name} ×{self.quantity_to_produce}"

    def get_required_materials(self) -> list[dict]:
        """
        Return list of {raw_material, quantity_needed} for this production run.
        quantity_needed = BOMItem.effective_quantity × (quantity_to_produce / bom.output_quantity)
        """
        scale = self.quantity_to_produce / self.bom.output_quantity
        return [
            {
                'raw_material': item.raw_material,
                'quantity_needed': (item.effective_quantity * scale).quantize(Decimal('0.001')),
                'unit': item.unit,
            }
            for item in self.bom.items.select_related('raw_material').all()
        ]
```

---

### `ProductionOrderItem` (in `manufacturing/models.py`)

```python
class ProductionOrderItem(models.Model):
    """
    Actual materials consumed in a completed production run.
    Created at completion time from BOM data + actual quantities.
    Serves as the permanent audit record of raw material consumption.
    """
    production_order = models.ForeignKey(
        ProductionOrder, on_delete=models.CASCADE, related_name='consumed_materials'
    )
    raw_material = models.ForeignKey(
        'products.Product', on_delete=models.PROTECT
    )
    quantity_planned = models.DecimalField(
        max_digits=12, decimal_places=3,
        help_text='Quantity from BOM calculation'
    )
    quantity_actual = models.DecimalField(
        max_digits=12, decimal_places=3,
        help_text='Actual quantity consumed (may differ due to waste)'
    )
    unit = models.CharField(max_length=20)
    unit_cost = models.DecimalField(
        max_digits=15, decimal_places=2,
        help_text='Cost per unit at time of production'
    )
    line_cost = models.DecimalField(
        max_digits=15, decimal_places=2,
        help_text='quantity_actual × unit_cost'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.production_order.order_number} ← {self.quantity_actual} {self.unit} {self.raw_material.name}"
```

---

### `WorkInProgress` (in `manufacturing/models.py`)

```python
class WorkInProgress(models.Model):
    """
    Snapshot of a production order's progress at a point in time.
    Purely informational — does not affect stock.
    """
    production_order = models.ForeignKey(
        ProductionOrder, on_delete=models.CASCADE, related_name='wip_snapshots'
    )
    snapshot_date = models.DateField()
    materials_consumed_value = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0'),
        help_text='Estimated value of materials used so far'
    )
    percentage_complete = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text='Estimated completion percentage (0–100)'
    )
    notes = models.TextField(blank=True)
    recorded_by_id = models.IntegerField(help_text='User ID who recorded this snapshot')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-snapshot_date']
        indexes = [
            models.Index(fields=['production_order', 'snapshot_date']),
        ]

    def __str__(self):
        return f"{self.production_order.order_number} WIP — {self.percentage_complete}% ({self.snapshot_date})"
```

---

## Endpoints

### `GET /api/manufacturing/boms/`

List BOMs. Filter by `is_active`, `finished_product`. Search by `name`.

**Permissions**: `IsAuthenticated`

**Response (200 OK)**:
```json
{
  "count": 8,
  "results": [
    {
      "id": 2,
      "name": "Standard Bread Loaf BOM v2",
      "finished_product": {"id": 15, "name": "Bread Loaf", "sku": "BKR-001"},
      "output_quantity": "10.000",
      "output_unit": "loaves",
      "unit_cost": "1850",
      "version": "2.0",
      "is_active": true,
      "items_count": 4
    }
  ]
}
```

---

### `POST /api/manufacturing/boms/`

Create a new BOM with its items.

**Permissions**: `IsAdminOrManager`

**Request body**:
```json
{
  "name": "Standard Bread Loaf BOM v2",
  "finished_product_id": 15,
  "output_quantity": "10.000",
  "output_unit": "loaves",
  "version": "2.0",
  "items": [
    {"raw_material_id": 22, "quantity_required": "2.500", "unit": "kg", "waste_factor_pct": "5.00"},
    {"raw_material_id": 18, "quantity_required": "0.100", "unit": "kg", "waste_factor_pct": "0.00"},
    {"raw_material_id": 31, "quantity_required": "1.500", "unit": "l",  "waste_factor_pct": "2.00"}
  ]
}
```

**Logic**: Create BOM + items in `transaction.atomic()`. Call `bom.compute_unit_cost()` and save.

**Response (201 Created)**: Full BOM object with items.

---

### `PATCH /api/manufacturing/boms/{id}/`

Update BOM name, version, output quantity, or items. Recomputes `unit_cost`.

**Permissions**: `IsAdminOrManager`

**Note**: Replacing items follows same pattern as `update-bom` in café — delete existing, create new.

---

### `GET /api/manufacturing/boms/{id}/cost/`

Cost breakdown per BOM.

**Permissions**: `IsAdminOrManager` or `IsAccountant`

**Response (200 OK)**:
```json
{
  "bom": "Standard Bread Loaf BOM v2",
  "finished_product": "Bread Loaf",
  "output_quantity": "10.000 loaves",
  "total_batch_cost": "18500",
  "unit_cost": "1850",
  "items": [
    {
      "raw_material": "Wheat Flour",
      "quantity_required": "2.500 kg",
      "waste_factor_pct": "5.00",
      "effective_quantity": "2.625 kg",
      "unit_cost": "4000",
      "line_cost": "10500"
    }
  ]
}
```

---

### `GET /api/manufacturing/orders/`

List production orders. Filter by `status`, `bom`, `outlet`.

**Permissions**: `IsAdminOrManager`

---

### `POST /api/manufacturing/orders/`

Create production order.

**Permissions**: `IsAdminOrManager`

**Request body**:
```json
{
  "bom_id": 2,
  "quantity_to_produce": "50.000",
  "outlet_id": 1,
  "planned_start": "2026-05-01T06:00:00Z",
  "notes": "Morning shift production batch"
}
```

**Logic**: Auto-generate `order_number` (MFG-YYYYMMDD-XXXX). Set `status='draft'`.

**Response (201 Created)**:
```json
{
  "id": 12,
  "order_number": "MFG-20260501-0012",
  "bom": {"id": 2, "name": "Standard Bread Loaf BOM v2"},
  "quantity_to_produce": "50.000",
  "status": "draft",
  "required_materials": [
    {"raw_material": "Wheat Flour", "quantity_needed": "13.125 kg", "available": "20.000 kg", "sufficient": true}
  ]
}
```

---

### `POST /api/manufacturing/orders/{id}/start/`

Start production. Sets `status='in_progress'`. Does NOT deduct stock.

**Permissions**: `IsAdminOrManager`

**Validation**: Order must be in `draft` status.

**Response (200 OK)**:
```json
{"status": "in_progress", "actual_start": "2026-05-01T06:15:00Z"}
```

---

### `POST /api/manufacturing/orders/{id}/complete/`

Complete production. Deducts raw material stock, adds finished product stock.

**Permissions**: `IsAdminOrManager`

**Request body** (optional — allows actual quantities to differ from planned):
```json
{
  "quantity_produced": "48.000",
  "notes": "2 loaves rejected due to underbaking"
}
```

**Logic** (ALL inside `transaction.atomic()`):

**Step 1 — Pre-flight check (before any writes)**:
```python
scale = quantity_to_produce / bom.output_quantity
shortages = []
for item in bom.items.all():
    needed = item.effective_quantity * scale
    stock = OutletStock.objects.filter(
        outlet=order.outlet, product=item.raw_material
    ).select_for_update().first()
    available = stock.quantity if stock else Decimal('0')
    if available < needed:
        shortages.append({
            'product': item.raw_material.name,
            'required': str(needed),
            'available': str(available)
        })
if shortages:
    raise ValidationError({'shortages': shortages})
```

**Step 2 — Deduct raw materials**:
- For each BOM item: `OutletStock.objects.filter(...).update(quantity=F('quantity') - quantity_needed)`
- Create `StockAuditLog` entry (source='manufacturing', source_id=order.id, change=-quantity_needed)

**Step 3 — Add finished product**:
- `OutletStock.objects.update_or_create(outlet=order.outlet, product=bom.finished_product)` → increment by `quantity_produced`
- Create `StockAuditLog` entry (source='manufacturing', source_id=order.id, change=+quantity_produced)

**Step 4 — Create ProductionOrderItem records**:
- One record per BOM item with actual quantities and costs at time of production

**Step 5 — Update order**:
- `total_material_cost = sum(item.line_cost for item in consumed_materials)`
- `status='completed'`, `completed_at=now()`, `quantity_produced=quantity_produced`

**Response (200 OK)**:
```json
{
  "status": "completed",
  "quantity_produced": "48.000",
  "total_material_cost": "88800",
  "unit_cost": "1850",
  "materials_consumed": [
    {"raw_material": "Wheat Flour", "quantity_actual": "12.600 kg", "line_cost": "50400"}
  ]
}
```

**Error (400 Bad Request)**:
```json
{
  "error": "Insufficient raw material stock",
  "shortages": [
    {"product": "Wheat Flour", "required": "13.125 kg", "available": "10.000 kg"}
  ]
}
```

---

### `POST /api/manufacturing/orders/{id}/wip/`

Log a WIP snapshot. Does not affect stock.

**Permissions**: `IsAuthenticated`

**Request body**:
```json
{
  "snapshot_date": "2026-05-01",
  "percentage_complete": "40.00",
  "materials_consumed_value": "35000",
  "notes": "Dough mixed; in ovens"
}
```

---

## Management Command: `update_bom_costs`

Recalculates `unit_cost` on all active BOMs based on current product cost prices.

```bash
docker compose exec backend python manage.py update_bom_costs
```

**Logic**:
1. For each active `BillOfMaterials`:
   - Call `bom.compute_unit_cost()`
   - If computed cost differs from stored `unit_cost`: update and log
2. Log summary: "Updated X BOMs. Y unchanged."

**Idempotency**: Safe to run multiple times — only writes when cost differs.

**File**: `manufacturing/management/commands/update_bom_costs.py`

---

## Finance Integration (Optional)

When completing a production order, optionally create journal entries:

```python
# Debit: Work in Progress / Production Cost (expense account)
# Credit: Raw Material Inventory (asset account)
# Then on completion:
# Debit: Finished Goods Inventory (asset account)
# Credit: Work in Progress (clears WIP)
```

This requires knowing the GL account codes per product category. Implement as an optional `--journal` flag on the `complete` action, defaulting to off.

---

## Security & Validation

1. **Tenant isolation**: All models are tenant-scoped
2. **Atomic completion**: `transaction.atomic()` wraps the entire `complete` action — ALL stock deductions or NONE
3. **Pre-flight check before writes**: Check ALL ingredients for sufficient stock BEFORE deducting any
4. **`select_for_update()`**: Lock `OutletStock` rows during completion to prevent concurrent deductions
5. **BOM version stability**: ProductionOrderItem records capture quantities at production time — BOM changes don't affect completed orders
6. **Inactive BOM guard**: Production orders cannot be created from `is_active=False` BOMs
7. **Status guards**: `start` requires `draft`; `complete` requires `in_progress`; cancelled orders cannot be restarted
8. **Effective quantity**: Always use `BOMItem.effective_quantity` (with waste factor), never `quantity_required` directly

---

## Tests (~40 test cases)

### Location: `manufacturing/tests.py` — use `TenantTestCase` + `TenantClient`

#### BillOfMaterials Tests
- [ ] `test_create_bom_with_items` — BOM + items created in one request
- [ ] `test_bom_requires_active_finished_product` — product must exist
- [ ] `test_one_bom_per_product_enforced` — OneToOneField constraint
- [ ] `test_compute_unit_cost_sums_ingredients` — (batch cost / output_qty) computed correctly
- [ ] `test_compute_unit_cost_includes_waste_factor` — effective_quantity used
- [ ] `test_bom_item_effective_quantity` — quantity_required * (1 + waste_factor/100)
- [ ] `test_update_bom_replaces_items` — PATCH replaces items + recomputes cost
- [ ] `test_inactive_bom_cannot_create_production_order` — 400 error

#### Cost Breakdown Tests
- [ ] `test_cost_endpoint_returns_per_item_breakdown` — each ingredient shown
- [ ] `test_cost_endpoint_shows_effective_quantities` — waste factor visible
- [ ] `test_cost_endpoint_requires_manager` — cashier gets 403

#### ProductionOrder Tests
- [ ] `test_create_production_order_generates_order_number` — MFG-YYYYMMDD-XXXX format
- [ ] `test_create_order_shows_required_materials` — materials + availability shown
- [ ] `test_create_order_sets_draft_status` — default status
- [ ] `test_start_order_sets_in_progress` — status transitions
- [ ] `test_start_order_requires_draft_status` — in_progress order cannot be restarted
- [ ] `test_cancel_draft_order` — status → cancelled, no stock change
- [ ] `test_list_orders_filter_by_status` — filter works
- [ ] `test_list_orders_filter_by_outlet` — outlet filter works

#### Complete Order Tests (core logic)
- [ ] `test_complete_order_deducts_raw_material_stock` — OutletStock decremented
- [ ] `test_complete_order_adds_finished_product_stock` — OutletStock incremented
- [ ] `test_complete_order_applies_waste_factor_in_deduction` — effective_quantity used
- [ ] `test_complete_order_creates_production_order_items` — audit records created
- [ ] `test_complete_order_computes_total_material_cost` — sum of line_costs correct
- [ ] `test_complete_order_creates_stock_audit_logs` — StockAuditLog entries created
- [ ] `test_complete_order_insufficient_stock_returns_400` — shortage error returned
- [ ] `test_complete_order_insufficient_one_material_rolls_back_all` — atomic rollback
- [ ] `test_complete_order_no_partial_deductions` — all or nothing verified
- [ ] `test_complete_order_updates_status_and_timestamps` — completed_at set
- [ ] `test_complete_order_custom_quantity_produced` — quantity_produced from body
- [ ] `test_complete_order_requires_in_progress_status` — draft order cannot be completed

#### WorkInProgress Tests
- [ ] `test_create_wip_snapshot` — 201 created
- [ ] `test_wip_percentage_must_be_0_to_100` — validation
- [ ] `test_wip_does_not_affect_stock` — OutletStock unchanged after WIP log
- [ ] `test_multiple_wip_snapshots_per_order` — history tracked

#### Management Command Tests
- [ ] `test_update_bom_costs_recalculates_unit_cost` — cost updated from product prices
- [ ] `test_update_bom_costs_idempotent` — running twice does not corrupt data
- [ ] `test_update_bom_costs_skips_inactive_boms` — is_active=False skipped

---

## Quality Checklist

- [ ] All models have `__str__`, `ordering`, `Meta.indexes`
- [ ] `BOMItem.effective_quantity` uses `Decimal` throughout (no `float`)
- [ ] `ProductionOrder.get_required_materials()` scales by `quantity_to_produce / bom.output_quantity`
- [ ] `complete` action checks ALL ingredients before ANY deduction
- [ ] `select_for_update()` used on OutletStock rows during completion
- [ ] `transaction.atomic()` wraps the entire complete action
- [ ] `StockAuditLog` entries created for every stock change
- [ ] `update_bom_costs` command is idempotent
- [ ] Inactive BOM guard on production order creation
- [ ] Status machine enforced: draft→in_progress→completed; draft→cancelled
- [ ] 40+ tests passing
- [ ] Security review completed
- [ ] Documentation: `docs/modules/manufacturing.md`

---

## Traps to Avoid

1. **Check all before deducting any**: The most critical invariant — never deduct stock for ingredient A then fail on ingredient B. Collect all shortages first, return 400 if any exist, then begin deductions.
2. **Use `select_for_update()`**: Lock OutletStock rows at the start of the complete action to prevent two simultaneous production orders from double-consuming the same stock.
3. **Waste factor in stock check**: Use `item.effective_quantity`, not `item.quantity_required`, in both the pre-flight check AND the actual deduction.
4. **Scale by production quantity**: BOM quantities are per `bom.output_quantity` batch, not per unit — always multiply by `quantity_to_produce / bom.output_quantity`.
5. **OutletStock missing**: If no `OutletStock` record exists for an ingredient at the outlet, treat as 0 quantity (not "skip") — otherwise it passes the stock check and fails silently.
6. **Finished product OutletStock**: Use `update_or_create` for the finished product — it may not have an OutletStock record yet.
7. **BOM version freeze**: Once a production order is started, the BOM quantities are locked by the `ProductionOrderItem` records created at completion — do not re-read BOM items if the BOM was updated mid-run.
8. **`unit_cost` is cached**: `bom.unit_cost` is only accurate after running `update_bom_costs` — do not treat it as real-time; product price changes require running the command.
9. **OneToOneField on finished_product**: If a product already has a BOM and you try to create another, Django raises `IntegrityError` — validate in the serializer before attempting create.
10. **`F()` for stock deduction**: Use `OutletStock.objects.filter(...).update(quantity=F('quantity') - needed)` — never read `stock.quantity`, subtract, and save (race condition).

---

## Files to Create

**New**:
- `backend/manufacturing/__init__.py`
- `backend/manufacturing/apps.py`
- `backend/manufacturing/models.py` — 5 models
- `backend/manufacturing/serializers.py`
- `backend/manufacturing/views.py`
- `backend/manufacturing/urls.py`
- `backend/manufacturing/admin.py`
- `backend/manufacturing/tests.py`
- `backend/manufacturing/management/__init__.py`
- `backend/manufacturing/management/commands/__init__.py`
- `backend/manufacturing/management/commands/update_bom_costs.py`
- `backend/manufacturing/migrations/0001_initial.py` (via `makemigrations`)

**Modified**:
- `backend/config/settings.py` — add `'manufacturing'` to `TENANT_APPS`
- `backend/api/urls.py` — add `path('manufacturing/', include('manufacturing.urls'))`

**Documentation**:
- `docs/modules/manufacturing.md`

---

## Delivery Checklist

- [ ] All 5 models implemented with migrations (`python manage.py makemigrations manufacturing`)
- [ ] Migrations run cleanly (`python manage.py migrate_schemas`)
- [ ] All 8 endpoints implemented and secured
- [ ] `complete` action is fully atomic — tested with intentional shortage
- [ ] Pre-flight shortage check returns structured error (not 500)
- [ ] `select_for_update()` applied to OutletStock in complete action
- [ ] `StockAuditLog` entries created for all stock movements
- [ ] `update_bom_costs` command functional and idempotent
- [ ] 40+ tests passing (`python manage.py test manufacturing`)
- [ ] Security review completed (`/security-review` skill)
- [ ] `python manage.py check` — no system errors
- [ ] `python manage.py migrate_schemas` — no errors
- [ ] Documentation: `docs/modules/manufacturing.md`
