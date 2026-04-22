# Backend Status

**Last Updated**: April 2026
**Phase**: 6 — Advanced Features Complete

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

## Infrastructure Updates
- **Multi-tenancy**: Self-service registration via `POST /api/tenants/register/`.
- **Security**: Hardened permission classes and role-based feature gating.
- **Docker**: Optimized for `pnpm` caching and named volumes for frontend speed.

## Upcoming (Phase 7)
- [ ] Pump hardware protocol integration (IFSF/Gilbarco/Wayne).
- [ ] Fleet Card / B2B module.
- [ ] Platform-wide analytics for Kakebe admin.

## Known Gaps
- Real EFRIS/Telco credentials needed for production environment variables.
