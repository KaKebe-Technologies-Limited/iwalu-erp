# Products & Categories Module

**App**: `products`
**Schema**: Tenant-isolated (each business has its own product catalog)
**Dependencies**: None (the `sales` module depends on this one)

---

## Purpose

The products module manages the complete product catalog across all business types. It uses a single `Product` model with a `Category` system that distinguishes items by business unit (fuel, cafe, supermarket, etc.). This unified approach means a tenant running both a fuel station and a cafe manages everything from one system.

Stock tracking is built in — products can be tracked by quantity (with decimal support for litres and kilograms), and the system automatically flags items that fall below their reorder level.

---

## Data Model

### Category

Hierarchical product categories, scoped by business unit.

| Field | Type | Description |
|-------|------|-------------|
| name | CharField(200) | Category name (e.g. "Petrol", "Hot Drinks", "Dairy") |
| business_unit | CharField(20) | One of: `fuel`, `cafe`, `supermarket`, `boutique`, `bridal`, `general` |
| description | TextField | Optional description |
| parent | FK -> self | Self-referential for subcategories (e.g. "Fuels" > "Petrol") |
| is_active | Boolean | Whether category is visible/usable |

**Design note**: `business_unit` on the category (not the product) allows the same product model to serve all business types. Filtering by `business_unit` gives you "all fuel products" or "all cafe items" without separate models.

### Product

The item being sold. Tracks pricing, tax, stock, and reorder levels.

| Field | Type | Description |
|-------|------|-------------|
| name | CharField(200) | Product name |
| sku | CharField(50), unique | Stock Keeping Unit — unique identifier |
| barcode | CharField(100) | Optional barcode for scanning |
| category | FK -> Category | Product category (PROTECT — can't delete category with products) |
| cost_price | Decimal(12,2) | Purchase/cost price |
| selling_price | Decimal(12,2) | Retail selling price |
| tax_rate | Decimal(5,2) | Tax percentage (e.g. 18.00 for 18% VAT) |
| track_stock | Boolean | Whether to track inventory for this item (default: true) |
| stock_quantity | Decimal(12,3) | Current stock level (3 decimal places for litres/kg) |
| reorder_level | Decimal(12,3) | Threshold for low stock alert |
| unit | CharField(10) | One of: `piece`, `litre`, `kg`, `metre`, `box`, `pack` |
| is_active | Boolean | Whether product is available for sale |

**Computed property**: `is_low_stock` — true when `track_stock` is enabled and `stock_quantity <= reorder_level`.

---

## Stock Management

Stock is modified in three ways:

1. **Sales** — Automatic deduction during checkout (`sales/services.py`). Uses `select_for_update()` to prevent race conditions.
2. **Void** — Automatic restoration when a sale is voided.
3. **Manual adjustment** — `POST /api/products/{id}/adjust_stock/` with a positive or negative quantity and a reason. Used for deliveries, spillage, breakage, or stock-takes.

The `stock_quantity` field uses 3 decimal places to support fractional units (e.g. 432.750 litres of petrol, 2.500 kg of sugar).

---

## API Endpoints

### Categories
| Method | Endpoint | Permission | Description |
|--------|----------|------------|-------------|
| GET | `/api/categories/` | Authenticated | List (filter: business_unit, parent, is_active; search: name) |
| POST | `/api/categories/` | Admin/Manager | Create category |
| GET | `/api/categories/{id}/` | Authenticated | Retrieve |
| PATCH | `/api/categories/{id}/` | Admin/Manager | Update |
| DELETE | `/api/categories/{id}/` | Admin/Manager | Delete |

### Products
| Method | Endpoint | Permission | Description |
|--------|----------|------------|-------------|
| GET | `/api/products/` | Authenticated | List (search: name, sku, barcode; filter: category, is_active, track_stock) |
| POST | `/api/products/` | Admin/Manager | Create product |
| GET | `/api/products/{id}/` | Authenticated | Retrieve (includes `category_name` and `is_low_stock`) |
| PATCH | `/api/products/{id}/` | Admin/Manager | Update |
| DELETE | `/api/products/{id}/` | Admin/Manager | Delete |
| GET | `/api/products/low_stock/` | Authenticated | Products at or below reorder level |
| POST | `/api/products/{id}/adjust_stock/` | Admin/Manager | Manual stock adjustment |

**Stock adjustment request**:
```json
{
  "quantity": "50.000",
  "reason": "Fuel delivery received"
}
```
Use negative values for reductions: `"quantity": "-5.000"` with `"reason": "Spillage"`.

---

## Permissions

| Action | Roles Allowed |
|--------|---------------|
| View products/categories | All authenticated users |
| Create/edit/delete products/categories | Admin, Manager only |
| Adjust stock | Admin, Manager only |

---

## Key Files

| File | Purpose |
|------|---------|
| `products/models.py` | Category and Product models |
| `products/serializers.py` | CategorySerializer, ProductSerializer, StockAdjustmentSerializer |
| `products/views.py` | CategoryViewSet, ProductViewSet with low_stock + adjust_stock actions |
| `products/urls.py` | URL routing |
| `products/tests.py` | 11 tests covering CRUD, permissions, search, low stock, stock adjustment |
| `products/admin.py` | Django admin with business_unit filtering |

---

## Used By

- **sales.SaleItem** — references product (and snapshots name/price at time of sale)
- **sales/services.py** — deducts stock during checkout, restores on void
