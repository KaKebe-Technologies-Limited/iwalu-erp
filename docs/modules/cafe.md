# Café & Bakery Management Module

The `cafe` app handles the full operational lifecycle of a café and bakery, including menu management, recipe-based stock deduction (BOM), order processing, and waste tracking.

## Models

### MenuCategory
Groups menu items (e.g., Hot Food, Drinks, Pastries).
- `name`: Unique name.
- `display_order`: Controls order on POS.
- `is_active`: Toggle visibility.

### MenuItem
A single sellable item.
- `price`: Selling price in UGX.
- `cost_price`: Auto-computed from BOM ingredients.
- `has_bom`: If True, stock is deducted on order.
- `is_available`: Availability toggle.

### MenuItemIngredient (BOM)
Links a MenuItem to inventory Products.
- `quantity_per_serving`: Amount to deduct from stock.
- `unit`: Measurement unit.

### MenuOrder
Represents a dine-in or takeaway order.
- `order_number`: Auto-generated (ORD-YYYYMMDD-XXXX).
- `status`: pending, preparing, ready, completed, cancelled.
- `total_amount`: Total order value.
- `outlet_id`: Required reference to the outlet where order is placed (for stock auditing).

### WasteLog
Records ingredient spoilage or expiry.
- `reason`: expired, spoiled, etc.
- `cost_value`: Estimated loss value.

## Key Workflows

### Order Creation
When a `MenuOrder` is created via `POST /api/cafe/orders/`:
1. The system validates all items and their availability.
2. For items with `has_bom=True`, it checks if sufficient stock exists in `OutletStock` for the specified outlet.
3. If stock is sufficient, it deducts the required quantities atomically inside a transaction.
4. Each stock movement is logged in `StockAuditLog`.

### Order Cancellation
If an order is moved to `cancelled` status:
1. The system identifies the original outlet from the audit logs.
2. It restores the deducted stock for all BOM items.
3. It logs the restoration as a `void` movement in `StockAuditLog`.

### Cost Recomputation
The `cost_price` of a `MenuItem` is computed as the sum of `product.cost_price * quantity_per_serving` for all its ingredients. It is updated whenever the BOM is changed via the `update-bom` action.

## Management Commands

### `check_cafe_expiry`
Analyzes `WasteLog` entries for the last 7 days. If a product has 3 or more expiry logs, it sends a high-priority notification to managers to review stock levels.

## Permissions
- **Admin/Manager**: Full access, including category/item management and cost reports.
- **Accountant**: Access to cost reports and waste logs.
- **Cashier/Attendant**: Can list menu items and manage orders.
