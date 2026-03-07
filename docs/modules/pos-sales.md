# POS & Sales Module

**App**: `sales`
**Schema**: Tenant-isolated (each business has its own sales data)
**Dependencies**: `outlets` (shift/sale tied to an outlet), `products` (items sold)

---

## Purpose

The POS (Point of Sale) module handles the complete sales cycle for all business types — fuel stations, cafes, supermarkets, boutiques, and bridal shops. It manages cashier shifts, processes multi-item transactions with split payments, applies discounts, tracks receipts, and provides sale history with void/refund capability.

This is the core revenue-generating module. Every transaction flows through it.

---

## Data Model

### Discount

Reusable discount definitions that can be applied at the sale level or individual item level.

| Field | Type | Description |
|-------|------|-------------|
| name | CharField(200) | Display name (e.g. "Staff 10%", "Weekend Promo") |
| discount_type | CharField | `percentage` or `fixed` |
| value | Decimal(10,2) | Percentage value (e.g. 10.00 for 10%) or fixed UGX amount |
| is_active | Boolean | Whether discount is currently usable |
| valid_from | DateTime | Optional start date |
| valid_until | DateTime | Optional expiry date |

### Shift

Represents a cashier's working session at a specific outlet. Every sale must belong to an open shift.

| Field | Type | Description |
|-------|------|-------------|
| outlet | FK -> Outlet | Which outlet this shift is at |
| user_id | Integer | Cashier's user ID (IntegerField, not FK — cross-schema limitation) |
| status | CharField | `open` or `closed` |
| opening_cash | Decimal(12,2) | Cash in the till at shift start |
| closing_cash | Decimal(12,2) | Actual cash counted at shift end |
| expected_cash | Decimal(12,2) | Calculated: opening_cash + all cash payments during shift |
| notes | TextField | Cashier notes on close (discrepancies, incidents) |
| opened_at | DateTime | Auto-set on creation |
| closed_at | DateTime | Set when shift is closed |

**Business rules**:
- A user can only have one open shift at a time
- Closing a shift automatically calculates expected cash from payment records
- The difference between `closing_cash` and `expected_cash` reveals discrepancies

### Sale

The transaction record. Created atomically by the checkout process.

| Field | Type | Description |
|-------|------|-------------|
| receipt_number | CharField(50), unique | Format: `OUT{outlet_id}-YYYYMMDD-NNNN` (e.g. `OUT1-20260307-0042`) |
| outlet | FK -> Outlet | Where the sale occurred |
| shift | FK -> Shift | Which shift this sale belongs to |
| cashier_id | Integer | Who processed the sale |
| subtotal | Decimal(12,2) | Sum of (unit_price * quantity) for all items, before tax and discounts |
| tax_total | Decimal(12,2) | Sum of tax across all items |
| discount_total | Decimal(12,2) | Sum of all discounts (item-level + sale-level) |
| grand_total | Decimal(12,2) | subtotal + tax_total - discount_total |
| discount | FK -> Discount | Optional sale-level discount applied |
| status | CharField | `completed`, `voided`, or `refunded` |
| notes | TextField | Optional sale notes |

### SaleItem

Individual line items within a sale. Snapshots product data at time of sale.

| Field | Type | Description |
|-------|------|-------------|
| sale | FK -> Sale | Parent sale |
| product | FK -> Product | The product sold (reference kept for reporting) |
| product_name | CharField(200) | Snapshot of product name at time of sale |
| unit_price | Decimal(12,2) | Snapshot of selling price at time of sale |
| quantity | Decimal(12,3) | Amount sold (3 decimal places for litres/kg) |
| tax_rate | Decimal(5,2) | Tax rate applied |
| tax_amount | Decimal(12,2) | Calculated tax for this line |
| discount | FK -> Discount | Optional item-level discount |
| discount_amount | Decimal(12,2) | Discount applied to this line |
| line_total | Decimal(12,2) | (unit_price * quantity) - discount + tax |

**Why snapshots?** Product names and prices change over time. The sale record preserves exactly what was sold and at what price, regardless of future product edits.

### Payment

One or more payments that cover a sale's grand total. Supports split payments.

| Field | Type | Description |
|-------|------|-------------|
| sale | FK -> Sale | Parent sale |
| payment_method | CharField | `cash`, `bank`, `mobile_money`, or `card` |
| amount | Decimal(12,2) | Amount paid via this method |
| reference | CharField(200) | Transaction reference (e.g. mobile money code, bank ref) |

---

## Business Logic

### Checkout Flow (`sales/services.py`)

The `process_checkout()` function is the heart of the POS system. It runs inside a database transaction with row-level locking to prevent race conditions (e.g. two cashiers selling the last unit of a product simultaneously).

**Step by step**:

1. **Validate discount** — If a sale-level discount ID is provided, verify it exists and is active
2. **For each item**:
   - Lock the product row (`select_for_update()`) to prevent concurrent stock issues
   - Verify sufficient stock (if `track_stock` is enabled)
   - Calculate line subtotal: `unit_price * quantity`
   - Apply item-level discount (if provided)
   - Calculate tax on the discounted amount: `(subtotal - discount) * tax_rate / 100`
   - Deduct stock immediately
3. **Calculate sale totals**:
   - `subtotal` = sum of all line subtotals (before discounts)
   - Apply sale-level discount to `(subtotal - item_discounts)`
   - `grand_total` = subtotal + tax_total - all discounts
4. **Validate payment** — Total paid must be >= grand_total
5. **Create records** — Sale, SaleItems, Payments (all within the atomic transaction)
6. **Generate receipt number** — `OUT{outlet_id}-YYYYMMDD-NNNN`, auto-incrementing per outlet per day

**If anything fails** (insufficient stock, insufficient payment, invalid discount), the entire transaction rolls back — no partial sales, no orphaned stock deductions.

### Discount Calculation

- **Percentage**: `subtotal * value / 100`, rounded to 2 decimal places
- **Fixed**: The lesser of the discount value or the subtotal (can't discount below zero)
- Discounts can be applied at two levels:
  - **Item-level**: Applied to individual line items before tax calculation
  - **Sale-level**: Applied to the post-item-discount subtotal

### Void Flow

When a sale is voided (admin/manager only):
1. Sale status is set to `voided`
2. Stock is restored for all items where `track_stock` is enabled
3. The sale record is preserved for audit purposes (never deleted)

### Shift Reconciliation

When closing a shift:
1. System sums all `cash` payments from sales in that shift
2. `expected_cash` = `opening_cash` + total cash payments
3. Cashier enters `closing_cash` (actual count)
4. Difference reveals shortages or overages

---

## API Endpoints

### Discounts
| Method | Endpoint | Permission | Description |
|--------|----------|------------|-------------|
| GET | `/api/discounts/` | Authenticated | List discounts (filter: discount_type, is_active) |
| POST | `/api/discounts/` | Admin/Manager | Create discount |
| GET | `/api/discounts/{id}/` | Authenticated | Retrieve discount |
| PATCH | `/api/discounts/{id}/` | Admin/Manager | Update discount |
| DELETE | `/api/discounts/{id}/` | Admin/Manager | Delete discount |

### Shifts
| Method | Endpoint | Permission | Description |
|--------|----------|------------|-------------|
| GET | `/api/shifts/` | Cashier+ | List shifts (filter: outlet, status) |
| POST | `/api/shifts/open/` | Cashier+ | Open a new shift |
| POST | `/api/shifts/{id}/close/` | Cashier+ | Close shift with cash count |
| GET | `/api/shifts/my_current/` | Cashier+ | Get current user's open shift |

### Checkout
| Method | Endpoint | Permission | Description |
|--------|----------|------------|-------------|
| POST | `/api/checkout/` | Cashier+ | Process a sale |

**Checkout request body**:
```json
{
  "items": [
    { "product_id": 1, "quantity": "10.000", "discount_id": null },
    { "product_id": 5, "quantity": "2.000" }
  ],
  "payments": [
    { "payment_method": "cash", "amount": "50000.00" },
    { "payment_method": "mobile_money", "amount": "20000.00", "reference": "MM-789456" }
  ],
  "discount_id": 3,
  "notes": "Customer requested receipt copy"
}
```

### Sales
| Method | Endpoint | Permission | Description |
|--------|----------|------------|-------------|
| GET | `/api/sales/` | Authenticated | List sales (search: receipt_number; filter: outlet, status, shift) |
| GET | `/api/sales/{id}/` | Authenticated | Sale detail with items + payments |
| POST | `/api/sales/{id}/void/` | Admin/Manager | Void sale and restore stock |
| GET | `/api/sales/{id}/receipt/` | Authenticated | Receipt data for printing |

---

## Permissions

"Cashier+" means admin, manager, cashier, or attendant. Accountants are excluded from POS operations — they can view sales data but cannot open shifts or process transactions.

| Action | Roles Allowed |
|--------|---------------|
| View sales/shifts/discounts | All authenticated users |
| Open/close shifts | Admin, Manager, Cashier, Attendant |
| Process checkout | Admin, Manager, Cashier, Attendant |
| Void a sale | Admin, Manager only |
| Create/edit discounts | Admin, Manager only |

---

## Key Files

| File | Purpose |
|------|---------|
| `sales/models.py` | Discount, Shift, Sale, SaleItem, Payment models |
| `sales/services.py` | `process_checkout()`, `generate_receipt_number()`, `apply_discount()` |
| `sales/serializers.py` | API serializers including CheckoutSerializer |
| `sales/views.py` | ViewSets for discounts, shifts, sales + checkout endpoint |
| `sales/urls.py` | URL routing |
| `sales/tests.py` | 15 tests covering checkout, stock, payments, discounts, shifts, void |
| `sales/admin.py` | Django admin with Sale inline items/payments |

---

## Test Coverage

The test suite (`sales/tests.py`) covers:

- Single item + cash payment (totals verified)
- Stock deduction after sale
- Insufficient stock rejection (400)
- Insufficient payment rejection (400)
- Multi-item + split payment (cash + mobile money)
- Percentage discount applied
- Fixed discount applied
- No open shift rejection (400)
- Accountant blocked from checkout (403)
- Void sale restores stock
- Shift expected cash calculation on close
- Shift open/close lifecycle
- Duplicate shift prevention
- Current shift lookup

All tests use `TenantTestCase` + `TenantClient` for tenant schema isolation.
