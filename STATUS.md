# Nexus ERP - Current Status

**Last Updated**: 4 April 2026
**Current Phase**: 6 — Advanced Features (Notifications & System Config Complete)
**Overall Progress**: ~90% (Phases 1-6b backend complete, frontend integration pending for Phases 5-6)

---

## Phase Completion Summary

| Phase | Name | Backend | Frontend | Status |
|-------|------|---------|----------|--------|
| 1 | Auth & Users | Done | Done | Complete |
| 2 | Outlets & Products | Done | Done | Complete |
| 3 | POS & Sales | Done | Hooks ready | Complete |
| 4 | Inventory & Reports | Done | Hooks + API wired | Complete |
| 5 | Finance & HR | Done | Pending | Backend Complete |
| 6a | Fuel Station Mgmt | Done | Pending | Backend Complete |
| 6b | Notifications & Config | Done | Pending | Backend Complete |
| 6c | Payments (Integrated) | Done | Pending | Backend Complete |
| 6d | Mobile Money (Direct) | Done | Pending | Backend Complete |
| 7a | Tenant Onboarding | Done | Pending | Backend Complete |
| 7b | SaaS Operations | Not started | Not started | Planned |
| 7c | Approval Workflows | Done | Pending | Backend Complete |
| 7d | Pump Hardware & Fleet | Not started | Not started | Future |
| 8a | Café & Bakery | Not started | Not started | Planned |
| 8c | Manufacturing & BOM | Done | Pending | Backend Complete |

---

## Frontend Screens — Status

### Authentication Pages (100% Complete)

| Screen | Route | Status |
|--------|-------|--------|
| Landing Page | `/` | Done — Full marketing site with pricing |
| Login | `/auth/login` | Done — Form validation, social login placeholders |
| Register | `/auth/register` | Done — Full registration flow with Zod validation |
| Forgot Password | `/auth/forgot-password` | Done — Email form + success state |
| Reset Password | `/auth/reset-password` | Done — Password requirements + success |

### Dashboard Layout (100% Complete)

| Feature | Status |
|---------|--------|
| Sidebar (260px, 9 nav items, 5 sections) | Done |
| Mobile responsive (off-canvas sidebar) | Done |
| User profile section (initials avatar, logout) | Done |
| Active route highlighting | Done |

### Module Pages

| Page | Route | Backend API | Frontend Hooks | UI |
|------|-------|-------------|----------------|-----|
| Dashboard Home | `/dashboard` | Done | Pending | Done (mock) |
| Sales | `/dashboard/sales` | Done | Done | Done (mock) |
| Products | `/dashboard/products` | Done | Done | Done (mock) |
| Discounts | `/dashboard/discounts` | Done | Done | Done (mock) |
| Outlets | `/dashboard/outlets` | Done | Done | Done (mock) |
| Shifts | `/dashboard/shifts` | Done | Done | Done (mock) |
| Inventory | `/dashboard/inventory` | Done | Done | Done (API wired) |
| Reports | `/dashboard/reports` | Done | Done | Done (API wired) |
| Fuel Station | `/dashboard/fuel` | Done | Pending | Done (mock) |
| POS | `/dashboard/pos` | Done | Pending | Done (mock) |
| Accounting | `/dashboard/accounting` | Done | Pending | Done (mock) |
| Employees | `/dashboard/employees` | Done | Pending | Done (mock) |
| Branches | `/dashboard/branches` | Partial (outlets API) | Pending | Done (mock) |
| Settings | `/dashboard/settings` | Pending | Pending | Done (mock) |

---

## Backend Modules

| Module | Models | Endpoints | Tests | Docs |
|--------|--------|-----------|-------|------|
| users | 1 | 9 | 9 | `docs/modules/auth-users.md` |
| outlets | 1 | 5 | 6 | `docs/modules/outlets.md` |
| products | 2 | 11 | 11 | `docs/modules/products.md` |
| sales | 5 | 11 | 15 | `docs/modules/pos-sales.md` |
| inventory | 7 | 13+ | 46+ | `docs/modules/inventory.md` |
| reports | 0 (aggregation) | 9 | 14 | `docs/modules/reports.md` |
| finance | 4 | 15 | 15 | `docs/modules/finance.md` |
| hr | 9 | 22 | 11 | `docs/modules/hr.md` |
| fuel | 6 | 18+ | ~40 | `docs/modules/fuel.md` |
| notifications | 3 | 12 | 20 | `docs/modules/notifications.md` |
| system_config | 3 | 11 | 18 | `docs/modules/system-config.md` |
| payments | 2 | 5 | 3 | — |
| tenants | 3 | 2 (register, verify-email) | 19 | `docs/modules/tenant-registration.md` |
| users (invitations) | +1 | 3 (invite, accept-invite, invitations) | +12 | `docs/modules/user-invitation.md` |
| fiscalization | 2 | 6 | ~25 | `docs/modules/fiscalization.md` |
| approvals | 3 | 8 | 6+ | `docs/modules/approvals.md` |
| manufacturing | 5 | 8 | 6 | `docs/modules/manufacturing.md` |

---

## Frontend Hooks

| Hook File | Queries | Mutations | Wired to Page |
|-----------|---------|-----------|---------------|
| `useProducts.ts` | products, lowStock | create, update, adjustStock | Inventory |
| `useCategories.ts` | categories | create, update, delete | Inventory |
| `useOutlets.ts` | outlets | create, update, delete | Outlets |
| `useSales.ts` | sales, receipt | checkout, void | Sales |
| `useShifts.ts` | shifts, myCurrent | open, close | Shifts |
| `useDiscounts.ts` | discounts | create, update, delete | Discounts |
| `useSuppliers.ts` | suppliers | create, update, delete | Inventory |
| `usePurchaseOrders.ts` | purchaseOrders | create, submit, receive, cancel | Inventory |
| `useStockTransfers.ts` | stockTransfers | create, dispatch, receive, cancel | Inventory |
| `useOutletStock.ts` | outletStock, lowStock | — | Inventory |
| `useStockAuditLog.ts` | auditLog | — | Inventory |
| `useReports.ts` | dashboard, salesSummary, salesByOutlet, salesByProduct, salesByPaymentMethod, hourlySales, stockLevels, stockMovement, shiftSummary | — | Reports |
| `useUsers.ts` | users | create, update, activate, deactivate | — |

---

## Package Manager

**Switched from npm to pnpm** (March 2026). `packageManager: pnpm@10.33.0` enforced via `package.json`.

---

## Next Steps (Priority Order)

### Phase 7a — Tenant Onboarding (Backend DONE, Frontend Pending)

**Backend complete**:
- `POST /api/tenants/register/` — creates tenant + sends verification email (admin stays inactive)
- `GET /api/tenants/verify-email/?token=` — activates admin, returns JWT + redirect_url
- `POST /api/users/invite/` — admin/manager sends staff invitation email
- `POST /api/users/accept-invite/` — invitee sets name+password, account created, JWT returned
- `GET /api/users/invitations/` — list pending/accepted invitations for current tenant
- Email backend configurable via `EMAIL_BACKEND` env var (console by default in dev)

**Frontend dev needs to build** (see `frontend/CLAUDE.md` Phase 7a section):
1. `/auth/verify-pending` — "check your email" screen shown after registration
2. `/auth/verify-email` — intercepts the verification link, calls backend, redirects to tenant subdomain
3. `/accept-invite` — form for invitees to set name+password (runs on tenant subdomain)
4. Invite staff modal + invitations list on Users/Employees page
5. `lib/hooks/useInvitations.ts` — `useInviteUser` + `useInvitations` hooks

### Phase 5 — Frontend Integration (Finance & HR) [frontend dev]
1. TypeScript interfaces for finance and HR models
2. TanStack Query hooks for accounts, journal entries, fiscal periods
3. TanStack Query hooks for employees, departments, leave, attendance, payroll
4. Wire Accounting page to live API
5. Wire Employees page to live API

### Phase 6b — Notifications & System Configuration (DONE)
6. ~~Notification models (in-app, email, SMS)~~
7. ~~Alert rules for low fuel, variance, low stock~~
8. ~~System configuration (tenant-level settings)~~

---

## Revised Roadmap (Post-Pesapal Competitive Analysis, April 2026)

Pesapal Forecourt Management is the primary Uganda competitor (Jan 2023 launch, Stabex lighthouse customer, pump-integrated payments + EFRIS + hardware control). Analysis drove the following re-prioritization:

### P0 — Go-to-market blockers

**a. EFRIS Integration (URA fiscal receipts)** — IN PROGRESS (Weaf-first approach).
- ✅ Research complete — see `docs/research/efris-integration.md`
- ✅ `fiscalization` Django app scaffolded with provider-agnostic architecture
- ✅ MockProvider working for dev/tests (deterministic FDN/QR)
- ✅ WeafProvider stub ready (HTTP plumbing, error handling, retry queue)
- ✅ Wired into `sales.process_checkout` (non-blocking)
- ✅ Fiscal data attached to `/api/sales/{id}/receipt/`
- ✅ Retry queue + cron-friendly `retry_efris` management command
- ⏳ Awaiting Weaf API credentials to complete real integration (contract pending)
- ⏳ Phase 2: direct URA accreditation (post-revenue)

**b. Phase 6c — Mobile Money (multi-provider)** — Matches Pesapal's core feature. Must be processor-agnostic (MTN MoMo + Airtel Money + Flutterwave ideally) to differentiate from Pesapal's payment lock-in.
- MTN MoMo Collections + Disbursements
- Airtel Money API
- Flutterwave aggregator as fallback
- Payment reconciliation with sales module
- Webhook handlers for async payment confirmations

### P1 — Critical gaps

**c. Pump hardware protocol integration** — Currently pumps/tanks are modelled logically. Real pump controllers (IFSF, Gilbarco, Wayne, Tokheim) need driver support to be competitive. Without this, Nexus is forecourt-lite.

**d. Tenant self-registration API** — DONE. Public `POST /api/tenants/register/` creates Client + Domain + first admin user atomically and returns JWT tokens. See `docs/modules/tenant-registration.md`.

**e. Role-based dashboard access** — Backend DONE. `GET /api/auth/me/permissions/` returns sections + actions for the current user's role. Role matrix lives in `backend/users/role_permissions.py`. Frontend dev needs to wire sidebar/route guards from this.

### P2 — Differentiation moats

**f. Fleet card module** — B2B moat for trucking companies and government vehicle fleets.
**g. Lighthouse customer case study** — Parity with Pesapal/Stabex reference.
**h. Convenience store / non-fuel retail polish** — Nexus's products+POS already works here; just needs UX polish to pitch alongside fuel.

### Differentiation angles to emphasize in sales/marketing

- **Full ERP depth** — Pesapal is forecourt + payments only. Nexus has double-entry accounting, HR/payroll, multi-tenant SaaS.
- **Payment-processor-agnostic** — Avoid Pesapal's lock-in by supporting any mobile money/card provider.
- **Local ownership** — Kakebe is Lira-based and Ugandan-owned.
- **Transparent SaaS pricing** — Pesapal is contact-sales only; published tiers attract smaller independents.

---

## Blockers

**Current**:
- EFRIS (URA) integration required before legal Uganda go-to-market
- Mobile money (Phase 6c) required for competitive parity with Pesapal
- Frontend login/register pages throw "Missing required parameter client_id" — Google OAuth SDK is initialized without `NEXT_PUBLIC_GOOGLE_CLIENT_ID`. Frontend dev needs to set the env var or defensively hide the Google button. This blocks UI-based testing until resolved; backend can still be tested via curl.
- Cashier shift-open reported failing with 403 — unblocked once frontend login works. Direct curl test recommended in the meantime.

---

**Update this file when significant milestones are reached.**
