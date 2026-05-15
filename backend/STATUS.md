# Backend Status

**Last Updated**: May 2026
**Phase**: 8 — Café, Projects, Manufacturing Complete

## Phase 4 (Complete)

### New Apps
- **inventory** — Suppliers, Purchase Orders, Stock Transfers, Outlet Stock levels, and Audit Logs.
- **reports** — Aggregated sales, inventory, and shift analytics.

### Key Endpoints
- `GET /api/products/low_stock/` — Global low stock report.
- `GET /api/inventory/audit-log/` — Immutable stock movement history.
- `GET /api/reports/dashboard/` — Multi-unit sales performance.

## Phase 5 (Complete)

### New Apps
- **finance** — Double-entry accounting (Chart of Accounts, Journal Entries, Fiscal Periods).
- **hr** — Employee records, Departments, Attendance (Clock-in/out), Leave Management, and Payroll.

### Key Endpoints
- `POST /api/finance/journal-entries/` — Manual and automated accounting entries.
- `GET /api/hr/payroll/` — Payroll generation and payslips.

## Phase 6 (Complete)

### New Apps
- **fuel** — Pump management, Tank tracking, Deliveries, and Daily Reconciliation.
- **notifications** — In-app, Email, and SMS notification system with templates.
- **system_config** — Tenant-level business rules and approval thresholds.
- **fiscalization** — EFRIS (URA) integration via Weaf provider.
- **payments** — Integrated Mobile Money (MTN, Airtel) and Card payments (Pesapal).

### Key Endpoints
- `POST /api/payments/initiate/` — Initiate collection (MTN/Airtel/Pesapal).
- `POST /api/payments/disburse/` — Direct Mobile Money disbursement.
- `GET /api/auth/me/permissions/` — Role-based access control (RBAC) definitions.

## Phase 7 (Complete)

### New Apps
- **approvals** — Multi-level approval workflows for high-value transactions.
- **assets** — Fixed asset tracking, depreciation, and disposal management.

### Key Endpoints
- `POST /api/approvals/approve/` — Approve pending transactions.
- `GET /api/assets/` — Asset inventory and depreciation schedules.

## Phase 8 (Complete)

### New Apps
- **cafe** — Menu management, recipe-level BOM, order lifecycle, waste tracking, expiry monitoring.
- **projects** — Project management, budgeting, expense tracking, time logging, profitability analysis.
- **manufacturing** — Bill of Materials, production orders, WIP tracking, unit costing, cost updates.

### Key Endpoints
- `POST /api/cafe/orders/` — Create order with atomic stock deduction.
- `GET /api/cafe/menu-items/{id}/cost/` — BOM-based cost breakdown.
- `POST /api/projects/` — Create project with budget approval workflow.
- `POST /api/projects/{id}/submit/` — Submit project for approval (if over threshold).
- `POST /api/manufacturing/orders/` — Create production order from BOM.
- `POST /api/manufacturing/orders/{id}/complete/` — Complete production, generate finished goods.

### Validations & Constraints
- **Café**: Atomic stock deduction, ingredient-level BOM, waste cost calculation, outlet requirement.
- **Projects**: Date validation, expense tracking with F() arithmetic, budget utilization tracking, state machine for project lifecycle.
- **Manufacturing**: Circular reference detection in BOMs, waste factor calculation, unit cost propagation, WIP to finished goods tracking.

## Infrastructure Updates
...
- **Multi-tenancy**: Self-service registration via `POST /api/tenants/register/`.
- **Security**: Hardened permission classes and role-based feature gating.
- **Docker**: Optimized for `pnpm` caching and named volumes for frontend speed.

## Upcoming Phases

### Phase 9 — Mobile API Layer ✅
- [x] `mobile_api` app — mobile JWT (cashier/attendant only, 5/min throttle), `IsMobileClient`/`IsNotMobileClient` permissions
- [x] `ShiftStartDataView` — outlet-scoped product/stock/discount/pump bundle (requires open shift at outlet)
- [x] `MobileSyncView` — idempotent batch sync (≤500 tx), per-tx atomicity, `select_for_update` stock deduction, `MobileSyncLog` audit, 10/min throttle
- [x] Shift close guard — `pending_mobile_transactions` field blocks close when > 0
- [x] `IsNotMobileClient` hardened on finance, HR, assets, users, tenants (30+ injection points)
- [x] `Sale.client_uuid` + `Sale.source` fields added with migrations
- [x] 42 tests — all passing
- Branch: `feat-phase-9-mobile-api` | Plan: `docs/plans/phase-9-mobile-api.md`

### Phase 10 — Reports & Analytics Completeness (Planned)
- [ ] HR/payroll reports (headcount, attendance, leave, payroll summary)
- [ ] Project performance and time-tracking reports
- [ ] EFRIS/tax compliance export (JSON + CSV)
- [ ] Role-based enhanced dashboard (admin/manager/accountant/cashier sections)
- Branch: `feat-phase-10-reports` | Plan: `docs/plans/phase-10-reports-analytics.md`

### Phase 11 — Inventory Enhancements (Planned)
- [ ] `ProductBatch` model — expiry date tracking with FIFO deduction at checkout
- [ ] Expiring-soon alert endpoint
- [ ] `Bundle` + `BundleItem` models — bridal/supermarket package sales
- [ ] Bundle checkout integration (expands to constituent products)
- Branch: `feat-phase-11-inventory-enhancements` | Plan: `docs/plans/phase-11-inventory-enhancements.md`

### Phase 12 — Finance Completeness (Planned)
- [ ] `Budget` + `BudgetLine` models — per-period/department budget with variance reporting
- [ ] Soft budget enforcement on cash requisitions
- [ ] `SupplierInvoice` + `APPayment` — accounts payable with AP aging report
- [ ] Outlet-level P&L filter on existing `profit_loss_view`
- Branch: `feat-phase-12-finance-completeness` | Plan: `docs/plans/phase-12-finance-completeness.md`

### Post-Phase-12 Backlog
- [ ] Pump hardware protocol integration (IFSF/Gilbarco/Wayne).
- [ ] Accounts receivable (credit customer invoicing).
- [ ] Fleet Card / B2B module.
- [ ] Platform-wide analytics dashboard for Kakebe admin.

## Testing
- **Backend**: 75+ unit tests covering Phases 1–9 (café, projects, manufacturing, mobile API).
- **Permissions**: Role-based access control tests for all action endpoints.
- **Data Integrity**: Atomic operations, race condition handling, F() arithmetic validation.

## Known Gaps
- Real EFRIS/Telco credentials needed for production environment variables.
- Frontend not yet implemented for Phase 8 modules; backend API ready for integration.
- Email/SMS delivery may require provider configuration in production.
