# Phase 8a Implementation Plan: Café & Bakery Management

**Backend only** (tenant-scoped, new `cafe` app)
**Estimated scope**: 6 models, 10 endpoints, 1 management command, ~40 tests
**New apps**: `cafe` (tenant-scoped)
**Tenant-scoped**: Yes

---

## Overview

Implements a full café and bakery operations module:
1. **Menu management**: Categories, items, availability toggling
2. **Recipe / BOM**: Ingredient-level stock deduction per menu item (Bill of Materials)
3. **Order management**: Dine-in and takeaway orders with status lifecycle
4. **Cost calculation**: Auto-computed cost price from BOM ingredients
5. **Waste tracking**: Ingredient waste/expiry logging with reasons
6. **Stock integration**: Deducts `inventory.OutletStock` atomically on order creation

Integrates with existing `products` (ingredients are `Product` objects), `inventory` (OutletStock), and optionally `sales` (POS handoff).

---

## Models

### `MenuCategory` (in `cafe/models.py`)

```python
class MenuCategory(models.Model):
    """
    Grouping for menu items (e.g. Drinks, Hot Food, Pastries, Combos).
    Admin-managed. Controls display order on POS/menu board.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name
```

---

### `MenuItem` (in `cafe/models.py`)

```python
class MenuItem(models.Model):
    """
    A single item on the café or bakery menu.
    If has_bom=True, creating an order deducts ingredients from OutletStock.
    cost_price is denormalised — recompute whenever BOM changes.
    """
    name = models.CharField(max_length=200)
    category = models.ForeignKey(
        MenuCategory, on_delete=models.PROTECT, related_name='items'
    )
    description = models.TextField(blank=True)

    # Pricing
    price = models.DecimalField(
        max_digits=15, decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        help_text='Selling price (UGX)'
    )
    cost_price = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0'),
        help_text='Computed from BOM ingredients. Update via update-bom action.'
    )

    # BOM toggle
    has_bom = models.BooleanField(
        default=False,
        help_text='True if ingredients must be deducted from stock on order'
    )

    # Availability
    is_available = models.BooleanField(
        default=True,
        help_text='Unavailable items cannot be ordered, even if in stock'
    )

    preparation_time_minutes = models.PositiveIntegerField(
        default=0,
        help_text='Estimated prep time; shown to kitchen staff'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'name']
        indexes = [
            models.Index(fields=['category', 'is_available']),
        ]

    def __str__(self):
        return f"{self.name} (UGX {self.price})"

    def recompute_cost_price(self):
        """Recompute and save cost_price from BOM ingredients."""
        if not self.has_bom:
            return
        total = sum(
            ing.product.cost_price * ing.quantity_per_serving
            for ing in self.ingredients.select_related('product').all()
            if hasattr(ing.product, 'cost_price') and ing.product.cost_price
        )
        self.cost_price = total
        self.save(update_fields=['cost_price', 'updated_at'])
```

---

### `MenuItemIngredient` (in `cafe/models.py`)

```python
class MenuItemIngredient(models.Model):
    """
    BOM line: links a MenuItem to an inventory Product.
    quantity_per_serving is deducted from OutletStock when ordered.
    """
    UNIT_CHOICES = [
        ('g', 'Grams'), ('kg', 'Kilograms'),
        ('ml', 'Millilitres'), ('l', 'Litres'),
        ('pcs', 'Pieces'), ('tbsp', 'Tablespoon'), ('tsp', 'Teaspoon'),
    ]

    menu_item = models.ForeignKey(
        MenuItem, on_delete=models.CASCADE, related_name='ingredients'
    )
    product = models.ForeignKey(
        'products.Product', on_delete=models.PROTECT,
        help_text='Inventory product used as ingredient'
    )
    quantity_per_serving = models.DecimalField(
        max_digits=12, decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
        help_text='How much of this product is used per serving'
    )
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['menu_item', 'id']
        unique_together = ('menu_item', 'product')

    def __str__(self):
        return f"{self.menu_item.name} ← {self.quantity_per_serving}{self.unit} {self.product.name}"
```

---

### `MenuOrder` (in `cafe/models.py`)

```python
class MenuOrder(models.Model):
    """
    A café/bakery order (dine-in or takeaway).
    Stock is deducted at creation time inside a transaction.
    """
    class OrderType(models.TextChoices):
        DINE_IN = 'dine_in', 'Dine-In'
        TAKEAWAY = 'takeaway', 'Takeaway'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending (received)'
        PREPARING = 'preparing', 'Being Prepared'
        READY = 'ready', 'Ready for Collection / Service'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    order_number = models.CharField(
        max_length=30, unique=True,
        help_text='Auto-generated: ORD-YYYYMMDD-XXXX'
    )
    order_type = models.CharField(max_length=10, choices=OrderType.choices)
    table_number = models.CharField(
        max_length=20, blank=True,
        help_text='Table reference for dine-in orders'
    )
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.PENDING
    )

    # Cashier who created the order (cross-schema IntegerField)
    cashier_id = models.IntegerField(help_text='User ID of cashier')

    total_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0'),
        help_text='Sum of order item line totals'
    )
    notes = models.TextField(blank=True, help_text='Special instructions for kitchen')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['order_type']),
        ]

    def __str__(self):
        return f"{self.order_number} ({self.get_order_type_display()}, {self.status})"
```

---

### `MenuOrderItem` (in `cafe/models.py`)

```python
class MenuOrderItem(models.Model):
    """
    A single line on a MenuOrder. Stock deduction happens at order creation.
    """
    order = models.ForeignKey(
        MenuOrder, on_delete=models.CASCADE, related_name='items'
    )
    menu_item = models.ForeignKey(
        MenuItem, on_delete=models.PROTECT
    )
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )
    unit_price = models.DecimalField(
        max_digits=15, decimal_places=2,
        help_text='Price at time of order (snapshot)'
    )
    line_total = models.DecimalField(max_digits=15, decimal_places=2)
    special_instructions = models.TextField(blank=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.quantity}× {self.menu_item.name} on {self.order.order_number}"

    def save(self, *args, **kwargs):
        self.line_total = self.unit_price * Decimal(self.quantity)
        super().save(*args, **kwargs)
```

---

### `WasteLog` (in `cafe/models.py`)

```python
class WasteLog(models.Model):
    """
    Records ingredient waste, spoilage, or expiry.
    Does NOT deduct stock (assumes stock was already consumed or adjusted separately).
    Used for reporting and trend analysis.
    """
    class Reason(models.TextChoices):
        EXPIRED = 'expired', 'Expired'
        SPOILED = 'spoiled', 'Spoiled'
        OVERPRODUCTION = 'overproduction', 'Overproduction'
        SPILLAGE = 'spillage', 'Spillage/Breakage'
        OTHER = 'other', 'Other'

    product = models.ForeignKey(
        'products.Product', on_delete=models.PROTECT,
        help_text='Ingredient/product that was wasted'
    )
    quantity = models.DecimalField(
        max_digits=12, decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))]
    )
    unit = models.CharField(max_length=10)
    reason = models.CharField(max_length=20, choices=Reason.choices)
    cost_value = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        help_text='Estimated loss value (quantity × cost price). Auto-computed if blank.'
    )

    recorded_by_id = models.IntegerField(help_text='User ID who logged the waste')
    recorded_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['product', 'recorded_at']),
            models.Index(fields=['reason']),
        ]

    def __str__(self):
        return f"{self.quantity}{self.unit} {self.product.name} — {self.get_reason_display()}"

    def save(self, *args, **kwargs):
        if self.cost_value is None and hasattr(self.product, 'cost_price') and self.product.cost_price:
            self.cost_value = self.product.cost_price * self.quantity
        super().save(*args, **kwargs)
```

---

## Endpoints

### `GET /api/cafe/menu-categories/`

List active menu categories.

**Permissions**: `IsAuthenticated`

**Response (200 OK)**:
```json
{
  "count": 4,
  "results": [
    {"id": 1, "name": "Hot Food", "description": "", "display_order": 1, "is_active": true}
  ]
}
```

---

### `POST /api/cafe/menu-categories/`

**Permissions**: `IsAdminOrManager`

**Request body**:
```json
{"name": "Pastries", "description": "Fresh daily bakes", "display_order": 2}
```

---

### `GET /api/cafe/menu-items/`

List menu items. Filter by `category`, `is_available`, `has_bom`. Search by `name`.

**Permissions**: `IsAuthenticated`

**Response (200 OK)**:
```json
{
  "count": 18,
  "results": [
    {
      "id": 3,
      "name": "Beef Pie",
      "category": {"id": 1, "name": "Hot Food"},
      "price": "5000",
      "cost_price": "2100",
      "has_bom": true,
      "is_available": true,
      "preparation_time_minutes": 5
    }
  ]
}
```

---

### `POST /api/cafe/menu-items/`

**Permissions**: `IsAdminOrManager`

**Request body**:
```json
{
  "name": "Beef Pie",
  "category_id": 1,
  "price": "5000",
  "has_bom": true,
  "preparation_time_minutes": 5
}
```

---

### `POST /api/cafe/menu-items/{id}/update-bom/`

Replace all BOM ingredients for a menu item. Recomputes `cost_price`.

**Permissions**: `IsAdminOrManager`

**Request body**:
```json
{
  "ingredients": [
    {"product_id": 12, "quantity_per_serving": "0.150", "unit": "kg"},
    {"product_id": 7,  "quantity_per_serving": "0.050", "unit": "kg"}
  ]
}
```

**Response (200 OK)**:
```json
{
  "status": "success",
  "cost_price": "2100",
  "ingredients_count": 2
}
```

**Logic**: Delete existing `MenuItemIngredient` records, create new ones, call `menu_item.recompute_cost_price()`.

---

### `GET /api/cafe/menu-items/{id}/cost/`

Cost breakdown for a menu item.

**Permissions**: `IsAdminOrManager` or `IsAccountant`

**Response (200 OK)**:
```json
{
  "menu_item": "Beef Pie",
  "selling_price": "5000",
  "cost_price": "2100",
  "gross_margin_pct": "58.00",
  "ingredients": [
    {"product": "Beef Mince", "quantity": "0.150 kg", "unit_cost": "12000", "line_cost": "1800"},
    {"product": "Pastry Flour", "quantity": "0.050 kg", "unit_cost": "6000", "line_cost": "300"}
  ]
}
```

---

### `POST /api/cafe/orders/`

Create order. Deducts ingredient stock atomically.

**Permissions**: `IsCashierOrAbove`

**Request body**:
```json
{
  "order_type": "dine_in",
  "table_number": "T3",
  "outlet_id": 1,
  "notes": "No onions on pie",
  "items": [
    {"menu_item_id": 3, "quantity": 2, "special_instructions": ""},
    {"menu_item_id": 9, "quantity": 1, "special_instructions": ""}
  ]
}
```

**Logic (inside `transaction.atomic()`)**:
1. Validate all `menu_item_id` exist and `is_available=True`
2. For each item where `has_bom=True`: check `OutletStock` has sufficient quantity for each ingredient
3. If any ingredient insufficient → rollback + 400 error listing the shortage
4. Deduct `OutletStock` for all BOM items
5. Create `MenuOrder` + `MenuOrderItem` records
6. Sum `line_total` → set `order.total_amount`

**Response (201 Created)**:
```json
{
  "id": 45,
  "order_number": "ORD-20260430-0045",
  "order_type": "dine_in",
  "table_number": "T3",
  "status": "pending",
  "total_amount": "15000",
  "items": [...]
}
```

**Error (400 Bad Request)**:
```json
{
  "error": "Insufficient stock",
  "shortages": [
    {"product": "Beef Mince", "required": "0.300 kg", "available": "0.200 kg"}
  ]
}
```

---

### `POST /api/cafe/orders/{id}/status/`

Advance order status. Allowed transitions:
- `pending` → `preparing`
- `preparing` → `ready`
- `ready` → `completed`
- any non-completed → `cancelled` (restores stock for BOM items)

**Permissions**: `IsCashierOrAbove`

**Request body**:
```json
{"status": "preparing"}
```

**Response (200 OK)**:
```json
{"id": 45, "status": "preparing", "message": "Order is now being prepared."}
```

**Cancellation logic**: If new status is `cancelled`, restore `OutletStock` for all BOM ingredients in the order.

---

### `GET /api/cafe/orders/`

List orders. Filter by `status`, `order_type`, `date`. Search by `order_number`.

**Permissions**: `IsCashierOrAbove`

---

### `GET/POST /api/cafe/waste-logs/`

**GET Permissions**: `IsAdminOrManager` or `IsAccountant`
**POST Permissions**: `IsAuthenticated`

**POST Request body**:
```json
{
  "product_id": 12,
  "quantity": "0.500",
  "unit": "kg",
  "reason": "expired",
  "notes": "Beef mince left over from yesterday — exceeded 24hr limit"
}
```

---

## Management Command: `check_cafe_expiry`

Run daily to identify products near expiry based on `WasteLog` trends.

```bash
docker compose exec backend python manage.py check_cafe_expiry
```

**Logic**:
1. Query `WasteLog` for `reason='expired'` entries in the last 7 days, grouped by `product`
2. Products with 3+ expired logs → send notification to managers
3. Log summary to stdout

**File**: `cafe/management/commands/check_cafe_expiry.py`

---

## Security & Validation

1. **Tenant isolation**: All `MenuCategory`, `MenuItem`, `MenuOrder`, `WasteLog` are tenant-scoped; no cross-tenant access possible
2. **Stock deduction atomicity**: Always inside `transaction.atomic()` — no partial deductions
3. **Availability enforcement at order time**: `is_available=False` returns 400, not just omits from listing
4. **Cost price snapshot**: `unit_price` on `MenuOrderItem` is snapshotted from `menu_item.price` at creation — price changes don't retroactively affect orders
5. **BOM ingredient product**: FKs to `products.Product` are within-schema (safe to use FK, not IntegerField)
6. **User references**: `cashier_id`, `recorded_by_id` are `IntegerField` (cross-schema)
7. **Waste cost auto-compute**: Only sets `cost_value` if blank and `product.cost_price` is available — never overwrites explicit values

---

## Tests (~40 test cases)

### Location: `cafe/tests.py` — use `TenantTestCase` + `TenantClient`

#### MenuCategory Tests
- [ ] `test_create_menu_category_as_admin` — 201 created
- [ ] `test_create_menu_category_as_cashier_forbidden` — 403
- [ ] `test_list_menu_categories_paginated` — 200, paginated
- [ ] `test_inactive_category_excluded_from_listing` — is_active=False hidden

#### MenuItem Tests
- [ ] `test_create_menu_item_no_bom` — has_bom=False, cost_price=0
- [ ] `test_create_menu_item_with_bom_flag` — has_bom=True, no ingredients yet
- [ ] `test_update_bom_replaces_ingredients` — POST update-bom/ deletes old, creates new
- [ ] `test_update_bom_recomputes_cost_price` — cost_price updated after BOM change
- [ ] `test_cost_endpoint_returns_breakdown` — GET /api/cafe/menu-items/{id}/cost/
- [ ] `test_cost_endpoint_requires_manager` — cashier gets 403
- [ ] `test_menu_item_search_by_name` — search param works
- [ ] `test_menu_item_filter_by_category` — category filter works
- [ ] `test_menu_item_filter_by_availability` — is_available filter works

#### MenuOrder Creation Tests
- [ ] `test_create_dine_in_order_deducts_stock` — OutletStock decremented for BOM items
- [ ] `test_create_takeaway_order_no_bom_no_deduction` — has_bom=False skips deduction
- [ ] `test_create_order_insufficient_stock_returns_400` — shortage error with details
- [ ] `test_create_order_insufficient_one_ingredient_rolls_back_all` — atomic rollback
- [ ] `test_create_order_unavailable_item_returns_400` — is_available=False rejected
- [ ] `test_create_order_generates_order_number` — ORD-YYYYMMDD-XXXX format
- [ ] `test_create_order_total_amount_computed` — sum of line totals
- [ ] `test_create_order_snapshots_price` — unit_price = menu_item.price at creation
- [ ] `test_create_order_multiple_items` — 3+ items, all BOM deductions applied
- [ ] `test_create_order_requires_cashier_permission` — attendant or above

#### MenuOrder Status Tests
- [ ] `test_status_pending_to_preparing` — valid transition
- [ ] `test_status_preparing_to_ready` — valid transition
- [ ] `test_status_ready_to_completed` — valid transition
- [ ] `test_status_invalid_transition_returns_400` — pending→completed invalid
- [ ] `test_cancel_order_restores_bom_stock` — OutletStock re-incremented
- [ ] `test_cancel_completed_order_returns_400` — cannot cancel completed

#### WasteLog Tests
- [ ] `test_create_waste_log` — 201 created
- [ ] `test_waste_log_auto_computes_cost_value` — quantity × product.cost_price
- [ ] `test_waste_log_explicit_cost_not_overwritten` — explicit cost_value respected
- [ ] `test_list_waste_logs_requires_manager` — cashier gets 403

#### Management Command Tests
- [ ] `test_check_cafe_expiry_no_alerts_if_few_logs` — no notification if < 3 logs
- [ ] `test_check_cafe_expiry_sends_notification_threshold` — notification sent at 3+ logs

---

## Quality Checklist

- [ ] All models have `__str__`, `ordering`, `Meta.indexes` where appropriate
- [ ] `MenuOrderItem.save()` computes `line_total`
- [ ] `MenuItem.recompute_cost_price()` uses `Decimal` throughout (no `float`)
- [ ] `WasteLog.save()` auto-sets `cost_value` only if blank
- [ ] All monetary fields use `DecimalField(max_digits=15, decimal_places=2)`
- [ ] Stock quantities use `DecimalField(max_digits=12, decimal_places=3)`
- [ ] `transaction.atomic()` wraps order creation and stock deduction
- [ ] Cancellation restores stock (reverse of creation logic)
- [ ] `cashier_id` and `recorded_by_id` are `IntegerField`, not ForeignKey
- [ ] `product` on `MenuItemIngredient` uses ForeignKey (within-schema, safe)
- [ ] `has_bom=False` → no stock deduction, no ingredient check
- [ ] Insufficient stock returns structured error, not 500
- [ ] `is_available=False` enforced at order creation (not just listing)
- [ ] 40+ tests passing
- [ ] Security review completed
- [ ] Documentation: `docs/modules/cafe.md`

---

## Traps to Avoid

1. **Float in cost calculation**: `recompute_cost_price` must use `Decimal()` throughout — never `float()`
2. **Missing availability check**: `is_available=False` must block ordering, not just hide from menu list
3. **Partial stock deduction**: Never deduct stock for item 1 then error on item 2 — check ALL, then deduct ALL in `transaction.atomic()`
4. **BOM on no-BOM item**: Check `has_bom` flag before any stock deduction — don't assume all items deduct stock
5. **Order total**: Set `total_amount` after all `MenuOrderItem` records are saved, not before
6. **Cost price on order**: Snapshot `menu_item.price` into `unit_price` at creation — never store a FK-based live price
7. **Waste log auto-cost**: Don't overwrite explicit `cost_value` — only compute when `None`
8. **OutletStock missing**: If product has no `OutletStock` record for the outlet, treat as 0 quantity, not as "skip check"
9. **`unique_together` on ingredients**: Updating BOM must delete all existing ingredients first, then re-insert — don't try to update in place

---

## Files to Create

**New**:
- `backend/cafe/__init__.py`
- `backend/cafe/apps.py`
- `backend/cafe/models.py` — 6 models
- `backend/cafe/serializers.py`
- `backend/cafe/views.py`
- `backend/cafe/urls.py`
- `backend/cafe/admin.py`
- `backend/cafe/tests.py`
- `backend/cafe/management/__init__.py`
- `backend/cafe/management/commands/__init__.py`
- `backend/cafe/management/commands/check_cafe_expiry.py`
- `backend/cafe/migrations/0001_initial.py` (via `makemigrations`)

**Modified**:
- `backend/config/settings.py` — add `'cafe'` to `TENANT_APPS`
- `backend/api/urls.py` — add `path('cafe/', include('cafe.urls'))`

**Documentation**:
- `docs/modules/cafe.md`

---

## Delivery Checklist

- [ ] All 6 models implemented with migrations (`python manage.py makemigrations cafe`)
- [ ] Migrations run cleanly (`python manage.py migrate_schemas`)
- [ ] All 10 endpoints implemented and secured
- [ ] Stock deduction is atomic (tested with intentional shortage)
- [ ] BOM cost recomputation works
- [ ] Management command functional and idempotent
- [ ] 40+ tests passing (`python manage.py test cafe`)
- [ ] Security review completed (`/security-review` skill)
- [ ] `python manage.py check` — no system errors
- [ ] Documentation complete: `docs/modules/cafe.md`
