# Architecture Reference — Nexus ERP

**System**: Nexus ERP  
**Company**: Kakebe Technologies, Lira, Uganda  
**Purpose**: Multi-tenant SaaS ERP for fuel stations and adjacent businesses  
**Last Updated**: May 2026  
**Maintainer**: Kakebe Technologies Engineering Team

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Decision Records](#2-architecture-decision-records)
3. [Data Flow Diagrams](#3-data-flow-diagrams)
4. [Deployment Architecture](#4-deployment-architecture)
5. [Security Architecture](#5-security-architecture)
6. [Module Dependency Graph](#6-module-dependency-graph)
7. [API Design Conventions](#7-api-design-conventions)

---

## 1. System Overview

Nexus ERP is a cloud-hosted, multi-tenant SaaS ERP system designed specifically for the Ugandan fuel station market. A single deployment serves multiple business tenants — each with complete data isolation — while sharing the authentication and billing infrastructure.

### Design Context

Uganda's fuel station landscape shapes nearly every architectural decision:

- **Connectivity**: 4G/3G coverage is inconsistent. Pump attendants work outdoors, often far from routers. The system must handle extended periods of no internet without breaking the transaction flow.
- **Hardware**: Most attendants carry basic Android phones. Smart POS terminals (Sunmi, PAX) are increasingly available at $150–300 per unit. Bank-issued POS terminals (Ingenico, Verifone) are locked ecosystems and cannot run custom apps.
- **Compliance**: The Uganda Revenue Authority (URA) mandates EFRIS fiscal receipts for all taxable sales from July 2025. Non-compliant businesses face penalties. Receipts must be fiscalized within hours of the sale.
- **Payments**: MTN Mobile Money and Airtel Money are the dominant payment methods for retail customers. Card payments are rare. Cash remains common.
- **Business model**: A single fuel station often operates a café, a supermarket, and a forecourt shop at one location. Nexus ERP handles all business types under one tenant.

### Tech Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Backend API | Django + DRF | 5.0 / 3.15 | REST API, business logic, ORM |
| Database | PostgreSQL | 16 | Multi-tenant schema isolation |
| Cache / Queue | Redis | 7 | Caching, task queues |
| Web Frontend | Next.js + TypeScript | 14 | Browser app (admin, manager, accountant) |
| Mobile App | React Native | 0.74+ | Native Android (cashier, attendant) |
| UI Components | shadcn/ui + Tailwind CSS | — | Web component library |
| State (web) | Zustand + TanStack Query | — | Auth state + API data caching |
| Local DB (mobile) | WatermelonDB (SQLite) | — | Offline-first transaction storage |
| Multi-tenancy | django-tenants | — | PostgreSQL schema-per-tenant |
| Containerization | Docker + docker compose | v2 | Development and production |

### Multi-Tenancy Model

Each tenant (business) is isolated in its own PostgreSQL schema. The `public` schema holds shared infrastructure (users, tenant registry, billing). All business data (sales, inventory, HR, etc.) lives in the tenant's private schema.

**Tenant routing**: Requests are routed by subdomain (`acme.nexus-erp.com`). The `TenantMainMiddleware` resolves the domain to a tenant, sets PostgreSQL `search_path`, and all subsequent ORM queries hit that tenant's isolated tables.

**Cross-schema FK limitation**: `users.User` lives in `public`; all tenant-scoped models that reference users use `IntegerField(user_id)` instead of a `ForeignKey`. The application layer enforces the relationship. This is a known constraint of schema-per-tenant and must be respected in all new models.

---

## 2. Architecture Decision Records

ADRs document the significant decisions made during system design. Each record captures the context, the decision, the alternatives rejected, and the consequences. Engineers should read these before proposing changes to the foundational architecture.

---

### ADR-001: Platform Strategy — Web + Native Mobile, Not PWA-First

**Status**: Accepted  
**Date**: 2025-Q4

#### Decision

- **Office staff** (admin, manager, accountant): Web browser application (Next.js). Full feature set, no offline requirement.
- **Operational staff** (cashier, attendant): Native Android app (React Native). Offline-first, shift-locked.
- **PWA**: Supported as a convenience supplement (e.g., for occasional manager access on a phone) but is not the primary offline solution for transactional staff.

#### Context

The initial instinct was to ship a single PWA to avoid maintaining two codebases. This was rejected after evaluating the Uganda hardware reality:

- **Service worker lifecycle**: Android OS aggressively kills background processes and service workers after 10–30 minutes of inactivity to preserve battery. A cashier who walks away from the till for 20 minutes can return to a dead service worker. Transactions during that window are lost.
- **IndexedDB storage limits**: Browsers on Android enforce per-origin storage quotas of approximately 50–100 MB. A single shift's transaction log can approach this limit once receipt images and EFRIS payloads are included. Quota exceeded = data loss.
- **ACID guarantees**: SQLite (WatermelonDB) offers full ACID transactions. IndexedDB provides weaker consistency semantics and its behavior under power loss varies by browser version and vendor.
- **Receipt printing**: Native SDKs (Sunmi InnerPrinter, Epson Bluetooth) are not accessible from a browser. Web Bluetooth is experimental, unreliable, and absent on most Android WebViews.
- **EFRIS compliance**: URA requires fiscal receipts to be issued at point of sale. If the web app's service worker is dead mid-transaction, there is no safe recovery path. A native app crash, by contrast, can recover from SQLite on restart.

#### Rejected Alternatives

| Alternative | Reason Rejected |
|-------------|----------------|
| PWA-only | Service worker killed by Android OS; IndexedDB quotas; no printer SDK access |
| Web-only (no offline) | Breaks at the pump when 4G drops; unacceptable for cashier workflow |
| Electron desktop | Fuel stations do not reliably have desktop PCs at pump points |
| Hybrid (Capacitor/Ionic) | Retains browser storage limits; no reliable SQLite access |

#### Consequences

- Two client codebases to maintain: Next.js (web) and React Native (mobile).
- Shared TypeScript types between web and mobile should be extracted into a `packages/shared` directory as the codebase grows.
- Feature parity: not all features need to be in both apps. The mobile app exposes only shift management, POS checkout, and EFRIS receipt printing.

---

### ADR-002: Offline Strategy — Shift-Locked, Manual Sync

**Status**: Accepted  
**Date**: 2025-Q4

#### Decision

The mobile app is **offline-first by default** during a shift. All transactions are written to local WatermelonDB (SQLite) first. Sync to the server is **user-triggered**, not automatic background sync.

The mandatory sync point is **shift close**. The shift close API call is blocked on the server if the server detects unsynced local transactions for that shift. Shift close is not permitted until the local database is fully flushed and the server has acknowledged all transaction IDs.

#### Context

The alternative — real-time or silent background sync — was rejected because:

- **Background sync on Android is unreliable**: Android's battery optimization kills background network operations unpredictably. Transactions silently fail to sync without the user's knowledge, creating a false sense of confirmed data.
- **Workflow alignment**: Cashier shift close already involves a physical reconciliation (cash count, reading pump meters). Requiring an explicit sync step at shift close fits naturally into the existing procedure and makes the data state visible to the cashier.
- **Conflict surface area**: Background sync requires complex conflict resolution logic. Shift-locked sync means conflicts are localized to one shift, visible to one cashier, and resolved in one transaction rather than being discovered days later.

#### Sync Rules

1. **App launch**: Check connectivity. If online, pull latest product catalog and pricing before shift start.
2. **Shift start**: Snapshot current product catalog into local DB. The snapshot is read-only for the duration of the shift (price changes on server do not affect in-progress shift).
3. **Each transaction**: Written to local WatermelonDB using deterministic UUID (`device_id + shift_id + counter`). Receipt printed from local data immediately.
4. **Mid-shift connectivity**: If internet is detected mid-shift, silently push pending transactions in a background queue (non-blocking to UI). This is opportunistic — not guaranteed.
5. **Shift close**:
   a. Block the shift close UI with a progress screen: "Syncing X pending transactions..."
   b. POST all pending transactions to server in batched requests.
   c. Flush EFRIS queue to URA API.
   d. Server confirms acknowledgement of all transaction IDs.
   e. Shift close allowed only after full confirmation.
6. **Post-sync**: Server returns consolidated shift summary (total sales, payment breakdown, EFRIS status). Display to cashier as the shift close report.

#### Server-Side Enforcement

The shift close endpoint checks:

```python
# Pseudocode
if ShiftTransaction.objects.filter(shift=shift, synced=False).exists():
    return Response({"error": "Unsynced transactions remain"}, status=409)
```

This prevents a race condition where the cashier closes the shift on the web dashboard while the mobile app still has local transactions.

#### Rejected Alternatives

| Alternative | Reason Rejected |
|-------------|----------------|
| Real-time sync per transaction | Requires stable internet at point of sale; breaks at pump |
| Silent background sync | Fails invisibly on Android; creates false confidence |
| No offline (server-first) | Unacceptable UX when 4G drops mid-transaction |

---

### ADR-003: POS Terminal Hardware Strategy

**Status**: Accepted  
**Date**: 2025-Q4

#### Decision

Use **unlocked Android devices only**. Do not attempt to use bank-issued locked POS terminals (Ingenico, Verifone older hardware).

#### Approved Hardware

**Fuel pump attendant**
- Primary: Sunmi P2 or Sunmi P2 Lite (smart Android POS, built-in 58mm thermal printer, rugged, IP54 rated)
- Alternative: Unlocked Android phone (Samsung Galaxy A-series or equivalent) + portable Bluetooth thermal printer
- Minimum spec: Android 8.0+, 2GB RAM, 16GB storage

**Shop till / café counter**
- Android tablet 8–10 inch (Samsung Galaxy Tab A7 or equivalent)
- Paired with Bluetooth thermal printer (Epson TM-T82 or RP80, 58mm roll)
- Tablet mounted on a stand with cash drawer connected to printer via RJ11

**Manager / office**
- Laptop or desktop browser (Next.js web app)
- No special hardware required

#### Kiosk Configuration

Android devices issued to attendants must be configured in kiosk/task-pinning mode at provisioning time:

1. Enable Android Device Policy (for MDM management) or use manual task pinning.
2. Lock device to the Nexus ERP app. Attendant cannot access the home screen, other apps, or settings during a shift.
3. Manager PIN required to exit kiosk mode (configured during device setup).
4. Screen wake lock enabled: device stays on during shift (disable auto-sleep in kiosk profile).

#### App Distribution

- Primary: Google Play Store (managed distribution via Google Play for Work for B2B).
- Secondary: APK side-loading via USB for devices without Play Store access.
- Updates: Play Store handles update delivery. Forced update check at app launch for critical security patches.

#### Receipt Printing

| Device Type | Printer Method | Library |
|-------------|---------------|---------|
| Sunmi P2 / PAX | Built-in InnerPrinter SDK | `react-native-sunmi-printer` (native bridge) |
| Android tablet + BT printer | Bluetooth ESC/POS | `react-native-bluetooth-escpos-printer` |
| Web browser | Browser print dialog or PDF | `react-to-print` |

Receipt width: 58mm thermal paper (standard in Uganda, widely available).

#### What NOT to Use

- **MTN/Airtel bank-issued POS terminals**: Locked bootloader, proprietary OS, cannot install third-party APKs. These are payment-only hardware.
- **iOS devices**: No offline SQLite library with the same guarantees as WatermelonDB on Android. App Store distribution is more complex for Uganda market. Not recommended unless explicitly requested.
- **Windows CE / legacy embedded POS**: Unsupported OS, no React Native support.

---

### ADR-004: Conflict Resolution Rules

**Status**: Accepted  
**Date**: 2025-Q4

#### Decision

Conflict resolution follows a **domain-aware** policy rather than a blanket "last write wins" or "server wins" rule.

| Data Type | Winner | Rationale |
|-----------|--------|-----------|
| Product prices & catalog | Server | Pricing is authoritative from the back office. Incorrect prices are a financial risk. |
| System configuration | Server | Tenant-level settings are managed centrally. |
| Transaction records (sales, payments) | Local | Transactions are append-only. A completed sale cannot be un-created. |
| EFRIS queue entries | Local | Fiscal records cannot be discarded. |
| Shift metadata (open/close status) | Server | Server is the system of record for shift lifecycle. |

#### Specific Conflict Scenarios

**Price drift**: Product price changed on server while attendant was offline.
- Action: Recalculate line totals using server price on sync.
- Flag the affected transactions for manager review (status: `price_adjusted`).
- Do NOT auto-void the sale — the transaction happened and must remain auditable.
- Notify manager in the dashboard: "3 transactions from Shift #42 had prices adjusted on sync."

**Duplicate transaction ID**: Same deterministic UUID appears twice (e.g., retry after timeout).
- Action: Server rejects the second POST with HTTP 409.
- Client marks the duplicate as `sync_conflict`, surfaces to manager.
- Manager resolves manually via dashboard.

**Shift force-closed on server** while attendant was offline (e.g., manager closed shift remotely):
- Action: Mobile app sync rejected with HTTP 409 + reason code `SHIFT_FORCE_CLOSED`.
- App enters "emergency sync" mode: transactions logged as `orphaned`, uploaded to a reconciliation queue.
- Manager must manually review and reconcile orphaned transactions.

**Attendant account deactivated while offline**:
- Transactions still sync to server (for audit completeness).
- After sync completes, session is invalidated.
- App displays "Your account has been deactivated. Contact your manager." and locks to login screen.

---

### ADR-005: EFRIS Offline Queue

**Status**: Accepted  
**Date**: 2025-Q4

#### Decision

Offline EFRIS fiscalization uses a **local queue with deterministic placeholder FDNs** (Fiscal Document Numbers). The queue is uploaded to the URA EFRIS API on the first available network connection — including opportunistic mid-shift uploads, not just at shift close.

Printed receipts produced offline carry a **"PENDING FISCALIZATION"** watermark until a confirmed FDN is received from URA. On confirmation, a replacement receipt can be re-printed with the official FDN.

#### Queue Lifecycle

```
Sale created
    │
    ▼
EFRIS entry created locally (status: pending)
    │
    ▼
Receipt printed with placeholder FDN + "PENDING FISCALIZATION" watermark
    │
    ▼
Network available? ──YES──► Upload to URA EFRIS API
    │                              │
    NO                        Confirmed? ──YES──► status: confirmed, FDN stored
    │                              │
    │                              NO ──► status: failed (retry up to 3×)
    ▼
Shift close
    │
    ▼
Block close until EFRIS queue empty (all status: confirmed)
    │
    ▼
Post-sync: re-print receipts with confirmed FDNs (optional, cashier-prompted)
```

#### Failure Escalation

- Retry count ≤ 3: Automatic retry with exponential backoff.
- Retry count > 3: Entry escalated to `failed` status. Manager alerted in dashboard.
- Manager can: retry manually, mark as manually fiscalized (with reference number from URA portal), or flag for compliance review.

#### Data Loss Risk

If a device is **lost or destroyed** before any sync occurs, EFRIS queue entries on that device are irrecoverable. Mitigation:

- Upload EFRIS queue on **every network reconnect event** during the shift, not only at shift close.
- Store a queue heartbeat record on the server (transaction IDs only, no PII) at shift start so the server knows what is expected.
- If shift close is never received for an open shift, server flags it after 24 hours for manual reconciliation.

#### URA Compliance Note

URA EFRIS mandate is effective July 2025. All taxable sales must have a fiscal receipt. "Pending fiscalization" receipts are technically non-compliant during the offline window but are the best available option given connectivity constraints. Legal advice obtained: URA field inspectors accept the pending watermark as evidence of good-faith compliance during documented connectivity outages.

---

### ADR-006: Session Management During Offline Shifts

**Status**: Accepted  
**Date**: 2025-Q4

#### Decision

JWT access tokens are **pre-fetched and stored encrypted on the device** at shift start. Token expiry during an offline period is **tolerated** — the app continues functioning. On reconnect, a **silent token refresh** is attempted. If the refresh fails (e.g., account deactivated, refresh token revoked), the user is allowed to **complete the current in-progress transaction** before being locked out.

#### Context

Access tokens expire after 1 hour. A fuel station cashier's shift is 8–12 hours. Requiring re-authentication every hour is unacceptable UX, and impossible when offline.

#### Implementation Details

- At shift start, the app stores both `access` and `refresh` tokens in **encrypted AsyncStorage** (AES-256, key derived from device biometric or PIN).
- The app maintains a local "session valid" flag. While offline, this flag is trusted.
- On any network reconnect:
  1. Attempt silent refresh: `POST /api/auth/refresh/` with the stored refresh token.
  2. On success: store new access and refresh tokens.
  3. On failure (401): set `session_invalid` flag.
- When `session_invalid` is set: allow current transaction to complete (do not interrupt a payment mid-flow), then lock to login screen.
- Shift close requires a valid token (forces online). If session is invalid, shift close also forces re-login.

#### Security Consideration

Storing refresh tokens on-device is a security trade-off. Mitigations:
- Tokens encrypted at rest (not plain AsyncStorage).
- Device must be in kiosk mode — physical access is controlled.
- Refresh tokens are single-use and rotated on each use.
- Remote token revocation is possible via admin dashboard (deactivating the user account invalidates all issued refresh tokens).

---

### ADR-007: Multi-Tenancy via PostgreSQL Schema-per-Tenant

**Status**: Accepted  
**Date**: 2025-Q3

#### Decision

Each tenant gets a dedicated PostgreSQL schema managed by `django-tenants`. Shared infrastructure (user accounts, tenant registry, subscription billing) lives in the `public` schema. All business data lives in the tenant's private schema.

#### Schema Layout

**Public schema** (shared across all tenants):
- `users.User` — all user accounts across all tenants
- `tenants.Client` — tenant registry
- `tenants.Domain` — subdomain-to-tenant mapping
- `tenants.Subscription`, `tenants.Invoice`, `tenants.UsageRecord` — billing
- `allauth` tables — social login
- Django admin, sessions, migrations

**Tenant schemas** (one per business, e.g., `acme`, `shell_lira`):
- outlets, products, sales, inventory, finance, hr, fuel, approvals, assets, notifications, system_config

#### Migration Rules

```bash
# ALWAYS use this — routes shared/tenant apps correctly:
python manage.py migrate_schemas

# NEVER use this — does not route to tenant schemas:
python manage.py migrate

# After adding a new app to TENANT_APPS:
python manage.py migrate_schemas --tenant
```

#### Cross-Schema FK Constraint

PostgreSQL cannot enforce foreign keys across schemas. Any model in a tenant schema that needs to reference a user must use:

```python
# Correct:
created_by = models.IntegerField(help_text="User ID from public schema")

# Wrong — will cause OperationalError in tenant context:
created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
```

The application layer resolves user objects by querying `public.users_user` directly when needed (e.g., for display in serializers).

#### Consequences

- Complete data isolation: a bug in one tenant's query cannot expose another tenant's data.
- Schema creation is fast (milliseconds) — tenant provisioning is automated.
- Backup granularity: individual tenant schemas can be backed up/restored independently.
- Reporting across tenants (for Kakebe admin dashboards) requires connecting to the `public` schema and iterating tenant schemas — this is intentional friction that prevents accidental cross-tenant data exposure.

---

## 3. Data Flow Diagrams

### Online Sale (Web or Mobile, Connected)

```
Cashier/Attendant
      │
      │ POST /api/checkout/
      ▼
Django API (DRF ViewSet)
      │
      ├──► Validate shift is open (Shift model)
      ├──► Validate products exist + calculate totals
      ├──► Validate payment amounts
      │
      ▼
PostgreSQL (tenant schema)
      │
      ├──► INSERT sales_sale
      ├──► INSERT sales_saleitem (× line items)
      ├──► INSERT sales_payment (× payment methods)
      ├──► UPDATE products_product.stock_quantity
      │
      ▼
Django API
      │
      ├──► Trigger EFRIS fiscalization task (async via Celery/Redis)
      │         │
      │         ▼
      │    URA EFRIS API
      │         │
      │    Receive FDN ──► UPDATE sales_sale.efris_fdn
      │
      └──► Return HTTP 201 { sale_id, receipt_data, efris_status }
              │
              ▼
          Client: Display receipt
```

---

### Offline Sale (Mobile App, No Connectivity)

```
Attendant (offline)
      │
      │ Tap "Complete Sale"
      ▼
React Native App
      │
      ├──► Generate deterministic UUID (device_id + shift_id + counter)
      ├──► Write to WatermelonDB (SQLite) — ACID transaction
      │       ├── transactions table (status: pending_sync)
      │       └── efris_queue table (status: pending)
      │
      ├──► Print receipt immediately (local data)
      │       └── "PENDING FISCALIZATION" watermark on receipt
      │
      └──► Return to cashier UI (< 200ms, no network call)

[ Later — internet detected mid-shift OR shift close initiated ]

React Native App
      │
      ├──► Opportunistic EFRIS queue upload (non-blocking)
      │       │
      │       ▼
      │    URA EFRIS API ──► status: confirmed, FDN stored locally
      │
      └──► At shift close: mandatory full sync (blocking)
                │
                ▼
          POST /api/shifts/{id}/sync/
                │
          Django API
                │
                ├──► Validate transaction IDs (no duplicates)
                ├──► INSERT all pending transactions
                ├──► UPDATE shift totals
                └──► Confirm all transaction IDs
                        │
                        ▼
                HTTP 200 { acknowledged: [...ids], shift_summary: {...} }
                        │
                        ▼
                React Native App: allow shift close
```

---

### Sync Flow at Shift Close (Detailed)

```
Cashier taps "Close Shift"
      │
      ▼
React Native: Pre-flight check
      ├── Count pending_sync transactions → N
      ├── Count pending EFRIS entries → M
      └── Display: "You have N transactions to sync before closing."

Cashier confirms
      │
      ▼
Phase 1: Transaction Sync
      ├── Batch POST pending transactions (50 per request)
      ├── Server returns: { accepted: [...], rejected: [...] }
      ├── rejected → flag for manager, surface in UI
      └── Loop until all accepted or max retries exceeded

Phase 2: EFRIS Flush
      ├── POST each pending EFRIS entry to URA API
      ├── On success: update local status to confirmed, store FDN
      ├── On failure: retry × 3, then escalate to manager
      └── Block shift close until all entries are confirmed or escalated

Phase 3: Shift Close
      ├── POST /api/shifts/{id}/close/
      ├── Server verifies: no pending sync records on server side
      ├── Server calculates: expected_total vs declared_total
      └── Returns: shift summary report

Phase 4: Post-Close
      ├── Display shift summary to cashier
      ├── Offer to re-print receipts with confirmed FDNs
      ├── Clear local WatermelonDB shift data
      └── Return to "Start New Shift" screen
```

---

## 4. Deployment Architecture

### Production Topology

```
Internet
    │
    ▼
Cloudflare (DNS + DDoS protection + CDN for static assets)
    │
    ├──► *.nexus-erp.com ──► Load Balancer
    │                              │
    │                         ┌────┴────┐
    │                         │         │
    │                    Django API  Django API   (horizontal scaling)
    │                         │         │
    │                         └────┬────┘
    │                              │
    │                    ┌─────────┼─────────┐
    │                    │         │         │
    │               PostgreSQL   Redis   Celery Workers
    │               (primary +   (cache   (EFRIS tasks,
    │                replica)     queue)    notifications)
    │
    ├──► app.nexus-erp.com ──► Next.js (Vercel or self-hosted Node)
    │
    └──► Google Play Store ──► React Native APK
```

### Service Breakdown

| Service | Technology | Scaling Strategy |
|---------|-----------|-----------------|
| API | Django + Gunicorn | Horizontal (stateless, JWT auth) |
| Web frontend | Next.js | CDN-distributed static export + SSR |
| Mobile app | React Native APK | Google Play Store delivery |
| Database | PostgreSQL 16 | Primary + read replica |
| Cache | Redis 7 | Single instance (Sentinel for HA) |
| Task queue | Celery + Redis | Worker pool, auto-scale on queue depth |

### Per-Tenant Subdomain Routing

```
acme.nexus-erp.com
    │
    ▼
Nginx / Load Balancer
    │
    ▼
Django TenantMainMiddleware
    │
    ├── SELECT * FROM public.tenants_domain WHERE domain = 'acme.nexus-erp.com'
    ├── Resolve to tenant: Client(schema_name='acme')
    └── SET search_path = acme, public
```

New tenant provisioning creates the PostgreSQL schema and runs migrations automatically:

```bash
python manage.py create_tenant \
  --schema_name acme \
  --name "ACME Fuel Station" \
  --domain-domain "acme.nexus-erp.com" \
  --domain-is_primary True
```

### Development Environment

```bash
docker compose up          # Starts: backend (:8000), frontend (:3000), db (:5432), redis (:6379)
docker compose build backend   # Only needed after requirements.txt changes
```

Code changes sync via Docker bind mounts — no rebuild required.

---

## 5. Security Architecture

### Authentication

- **Protocol**: JWT (JSON Web Tokens) via `djangorestframework-simplejwt`
- **Access token TTL**: 1 hour
- **Refresh token TTL**: 7 days (rotated on each use)
- **Storage (web)**: Zustand store with localStorage persistence
- **Storage (mobile)**: Encrypted AsyncStorage (AES-256, device-key derived)
- **Social login**: Google OAuth and Apple Sign-In via `django-allauth` — returns same `{ access, refresh }` pair

### Role-Based Access Control

| Role | Scope | Key Permissions |
|------|-------|----------------|
| Admin | Full tenant | All operations, user management, configuration |
| Manager | Operational | Approve workflows, void sales, view all reports |
| Accountant | Finance | Chart of accounts, journal entries, payroll, reports |
| Cashier | Shift-scoped | Open/close shifts, process sales, apply discounts |
| Attendant | Transaction-scoped | Process fuel sales, print receipts |

Permissions are enforced at the ViewSet level using custom DRF permission classes. No permission logic lives in serializers or models.

### Tenant Isolation

- PostgreSQL `search_path` is set per-request by middleware — a query in one request cannot accidentally access another tenant's schema.
- No shared in-memory state between tenants.
- Redis keys are namespaced by `tenant_id` to prevent cache poisoning across tenants.
- Celery tasks carry `tenant_schema_name` in their payload; worker sets `search_path` before executing.

### Audit Logging

All write operations (CREATE, UPDATE, DELETE) on business-critical models are logged to an `AuditLog` table in the tenant schema:

```
AuditLog { tenant_schema, user_id, action, model, object_id, changes_json, ip_address, timestamp }
```

Audit logs are append-only (no DELETE permission on the table at the DB level).

### Encrypted Local Storage (Mobile)

- WatermelonDB database file is encrypted using SQLCipher.
- Encryption key derived from a combination of device hardware ID and a server-issued per-device key.
- If the device is reported lost, the server revokes the per-device key — the local DB becomes unreadable.

### Secrets Management

- Development: `.env` files with `python-decouple`. Never committed to Git.
- Production: Environment variables injected at container startup (planned migration to Doppler or AWS Secrets Manager).
- No secrets in source code, Docker images, or logs.

---

## 6. Module Dependency Graph

```
public schema
├── tenants (Client, Domain, Subscription, Invoice)
└── users (User, social accounts)

tenant schema
├── system_config (TenantSettings) ◄── referenced by all modules
├── outlets (Outlet)
│   └── products (Category, Product, StockMovement)
│       ├── sales (Shift, Sale, SaleItem, Payment, Discount)
│       │   └── fiscalization (EFRISQueue, FiscalReceipt)
│       └── inventory (Supplier, PurchaseOrder, StockTransfer)
├── finance (Account, JournalEntry, CashRequisition)
│   └── approvals (ApprovalWorkflow, ApprovalRequest, ApprovalStep)
├── hr (Employee, Leave, Attendance, Payroll)
├── fuel (Pump, Tank, Dip, Reconciliation)
├── assets (FixedAsset, Depreciation)
├── notifications (Notification, NotificationTemplate)
└── payments (MoMoTransaction, PesapalTransaction)
```

Detailed module documentation is in `docs/modules/`:

| Module | Documentation |
|--------|--------------|
| Auth & Users | `docs/modules/auth-users.md` |
| Outlets | `docs/modules/outlets.md` |
| Products & Categories | `docs/modules/products.md` |
| POS & Sales | `docs/modules/pos-sales.md` |
| Inventory | `docs/modules/inventory.md` |
| Finance | `docs/modules/finance.md` |
| HR | `docs/modules/hr.md` |
| Fuel Management | `docs/modules/fuel.md` |
| Approvals | `docs/modules/approvals.md` |
| Fixed Assets | `docs/modules/assets.md` |
| Tenants & Billing | `docs/modules/tenants-billing.md` |

---

## 7. API Design Conventions

### URL Structure

```
/api/{resource}/              → List + Create
/api/{resource}/{id}/         → Retrieve + Update + Delete
/api/{resource}/{id}/{action}/ → Custom action
```

### Response Envelope

**List (paginated)**
```json
{
  "count": 100,
  "next": "https://api.nexus-erp.com/api/sales/?page=2",
  "previous": null,
  "results": [...]
}
```

**Single object**
```json
{
  "id": 42,
  "name": "...",
  "created_at": "2026-05-08T10:00:00Z",
  "updated_at": "2026-05-08T10:00:00Z"
}
```

**Error**
```json
{
  "error": "Shift is already closed.",
  "detail": "Shift #12 was closed at 2026-05-08T18:30:00Z by user 7."
}
```

### Pagination

Default page size: 20. Max page size: 100. Controlled via `?page_size=` query parameter.

### Filtering

All list endpoints support:
- `?search=` — full-text search on indexed fields (via `SearchFilter`)
- `?ordering=` — field-based ordering (via `OrderingFilter`)
- Field filters — via `django-filter` (e.g., `?status=open&outlet_id=3`)

### Documentation

Auto-generated from DRF ViewSets via `drf-spectacular`:

```
GET /api/docs/    → Swagger UI
GET /api/redoc/   → ReDoc
GET /api/schema/  → OpenAPI 3.0 JSON
```
