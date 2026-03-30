# Reports Module

**App**: `reports`
**Schema**: Tenant-isolated (queries tenant-specific data)
**Dependencies**: `sales` (Sale, SaleItem, Payment, Shift), `products` (Product), `inventory` (OutletStock, StockAuditLog)

---

## Purpose

The Reports module provides real-time analytics and KPIs by aggregating data from sales, inventory, and shift tables. It has no models of its own — all endpoints use Django ORM aggregation on existing tables.

---

## API Endpoints

### Dashboard KPIs
```
GET /api/reports/dashboard/
```
Role-scoped summary for today:
- **Admin/Manager**: Full overview (all outlets or filtered by outlet)
- **Cashier/Attendant**: Scoped to current open shift's outlet

Returns: `today_sales`, `today_revenue`, `active_shifts`, `low_stock_count`, `date`

### Sales Summary
```
GET /api/reports/sales-summary/?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&outlet=ID
```
Returns: `total_sales`, `total_revenue`, `total_tax`, `total_discount`, `avg_sale`

### Sales by Outlet
```
GET /api/reports/sales-by-outlet/?date_from=&date_to=
```
Returns array: `outlet`, `outlet_name`, `total_sales`, `total_revenue` (ordered by revenue desc)

### Sales by Product
```
GET /api/reports/sales-by-product/?date_from=&date_to=&outlet=&category=
```
Returns top 20 products: `product`, `product_name`, `product_sku`, `total_quantity`, `total_revenue`

### Sales by Payment Method
```
GET /api/reports/sales-by-payment-method/?date_from=&date_to=&outlet=
```
Returns array: `payment_method`, `count`, `total_amount`

### Hourly Sales
```
GET /api/reports/hourly-sales/?date_from=&date_to=&outlet=
```
Returns array: `hour`, `total_sales`, `total_revenue` (for intraday trend analysis)

### Stock Levels
```
GET /api/reports/stock-levels/?outlet=&category=
```
- With `outlet`: per-outlet stock (OutletStock join)
- Without `outlet`: aggregate product stock levels

### Stock Movement
```
GET /api/reports/stock-movement/?date_from=&date_to=&product=&outlet=
```
Returns movement summary by type: `movement_type`, `count`, `total_quantity`

### Shift Summary
```
GET /api/reports/shift-summary/?date_from=&date_to=&outlet=&user_id=
```
Returns closed shifts with sales totals and cash reconciliation data.

---

## Permissions

| Endpoint | Access |
|----------|--------|
| Dashboard | All authenticated (role-scoped data) |
| Sales Summary | All authenticated |
| Stock Levels | All authenticated |
| All other reports | Admin/Manager only |

---

## Query Parameters

All date-filtered endpoints accept:
- `date_from` — Start date (YYYY-MM-DD), defaults to today
- `date_to` — End date (YYYY-MM-DD), defaults to today
- `outlet` — Filter by outlet ID (where applicable)

---

## Frontend Integration

### Hooks (in `frontend/src/lib/hooks/useReports.ts`)
- `useDashboard()` — Dashboard KPIs
- `useSalesSummary()` — Sales overview
- `useSalesByOutlet()` — Outlet breakdown
- `useSalesByProduct()` — Top products
- `useSalesByPaymentMethod()` — Payment breakdown
- `useHourlySales()` — Intraday trends
- `useStockLevels()` — Stock data
- `useStockMovement()` — Movement summary
- `useShiftSummary()` — Shift reconciliation

### Page
- `app/dashboard/reports/page.tsx` — Live dashboard KPIs, date-filtered reports, category-based navigation (wired to real API)

---

## Test Coverage

14 test cases covering:
- Sales summary (basic + outlet-filtered)
- Sales by outlet, product, payment method
- Hourly sales trends
- Stock level aggregation
- Dashboard for admin vs cashier roles
- Unauthenticated access rejection
