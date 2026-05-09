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

## Upcoming (Phase 9 onwards)
- [ ] Frontend integration (Phases 5–8): Build Next.js UI for all completed backend modules.
- [ ] Pump hardware protocol integration (IFSF/Gilbarco/Wayne).
- [ ] Fleet Card / B2B module.
- [ ] Platform-wide analytics dashboard for Kakebe admin.
- [ ] Mobile app (React Native or Flutter) for field staff.

## Testing
- **Backend**: 33+ unit tests covering all Phase 8 modules (café, projects, manufacturing).
- **Permissions**: Role-based access control tests for all action endpoints.
- **Data Integrity**: Atomic operations, race condition handling, F() arithmetic validation.

## Known Gaps
- Real EFRIS/Telco credentials needed for production environment variables.
- Frontend not yet implemented for Phase 8 modules; backend API ready for integration.
- Email/SMS delivery may require provider configuration in production.
