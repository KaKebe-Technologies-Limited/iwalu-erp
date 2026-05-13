# Frontend Developer Guide — Nexus ERP

**Audience**: Frontend developer joining the Nexus ERP project  
**Project**: Multi-tenant Fuel Station ERP (Kakebe Technologies, Lira, Uganda)  
**Stack**: Next.js 14, TypeScript, TanStack Query, Zustand, shadcn/ui, Tailwind CSS  
**Backend**: Django 5.0 / DRF — running at `http://localhost:8000` in dev  
**Last Updated**: May 2026

---

## Current State

| Phase | Backend | Frontend |
|-------|---------|----------|
| 1 — Auth & Users | Complete | Partial |
| 2 — Outlets & Products | Complete | Partial |
| 3 — POS / Sales | Complete | Partial |
| 4 — Inventory | Complete | Partial |
| 5 — Finance / GL | Complete | **Not started** |
| 6 — HR & Payroll | Complete | **Not started** |
| 7a — Fuel Reconciliation | Complete | **Not started** |
| 7b — Subscription Billing | Complete | **Not started** |
| 7c — Approval Workflows | Complete | **Not started** |
| 7d — Asset Management | Complete | **Not started** |
| 8 — Café, Projects, Manufacturing | Stubs only | **Not started** |

The backend exposes Swagger at `/api/docs/` — verify every endpoint there before building UI. Phase 8 backend stubs exist but are not fully implemented; coordinate with the backend developer before building those UIs.

A separate React Native Android app is planned — see `docs/mobile-app-plan.md`. The mobile app scope is distinct from your work here.

---

## Critical Gaps to Fix First

### 1. Role-Based Dashboard Routing

**Problem**: A single dashboard landing page does not work. Each role needs a fundamentally different entry point. Showing a manager's overview to a cashier, or hiding the POS from an accountant, is a UX failure.

**Solution**: Route `/dashboard` to a role-specific page immediately on load.

```
/dashboard → (middleware redirect based on role)
  admin      → /dashboard/admin
  manager    → /dashboard/manager
  accountant → /dashboard/accounts
  cashier    → /dashboard/pos
  attendant  → /dashboard/pos
```

Each role's landing page shows only what is relevant:

- **Admin**: Tenant health, subscription status (Phase 7b), active users, system config, audit log link
- **Manager**: Today's sales across all outlets, pending approvals (Phase 7c), low stock alerts, staff currently on shift, cash float summary
- **Accountant**: Outstanding receivables, unposted journal entries, bank reconciliation status, EFRIS compliance alerts
- **Cashier / Attendant**: Current shift status (open or closed), today's sales count + total, "Open Shift" button if no active shift exists

**Implementation**:

In `middleware.ts`, read the role from the JWT or session cookie and redirect. Do not rely on client-side redirects alone — they cause a flash of wrong content.

```typescript
// middleware.ts
import { NextRequest, NextResponse } from 'next/server';
import { getRoleFromToken } from '@/lib/auth';

const ROLE_HOME: Record<string, string> = {
  admin: '/dashboard/admin',
  manager: '/dashboard/manager',
  accountant: '/dashboard/accounts',
  cashier: '/dashboard/pos',
  attendant: '/dashboard/pos',
};

export function middleware(request: NextRequest) {
  if (request.nextUrl.pathname === '/dashboard') {
    const role = getRoleFromToken(request);
    const target = ROLE_HOME[role] ?? '/dashboard/manager';
    return NextResponse.redirect(new URL(target, request.url));
  }
}
```

On the client side, read role from the Zustand auth store and conditionally render dashboard widgets.

---

### 2. POS — Separate Layout

**Problem**: The POS used by cashiers and attendants is not a dashboard. It is a full-screen, touch-optimised application. If you build it inside the sidebar/topbar dashboard layout, it will fail in use at a fuel station counter.

**Solution**: Create a completely separate Next.js layout group.

```
app/
  (dashboard)/     ← existing layout: sidebar + topbar
  (pos)/           ← NEW layout: no sidebar, no topbar, full-screen
    layout.tsx     ← touch-optimised shell
    pos/
      page.tsx     ← shift status / open shift
    pos/sale/
      page.tsx     ← product grid + cart
    pos/payment/
      page.tsx     ← payment method + MoMo flow
    pos/receipt/
      page.tsx     ← receipt display + print
    pos/shift/
      close/
        page.tsx   ← reconciliation form + close shift
```

**POS layout requirements**:

- No sidebar. No topbar. Shift status lives in the POS header itself.
- All interactive elements: minimum 48×48px touch target
- High contrast — fuel station environments have direct sunlight on screens
- Product buttons: large grid, not a searchable table
- Cart always visible on screen — no scrolling to find it
- Cash calculator: input amount tendered → auto-calculate and display change
- The entire POS must be usable with one hand on a tablet

Create `app/(pos)/layout.tsx` as a standalone shell. It shares the auth/Zustand context but nothing else from the dashboard layout.

---

### 3. Role-Filtered Navigation

**Problem**: The sidebar likely renders all menu items regardless of the logged-in user's role.

**Solution**: Define navigation with role constraints and filter before render.

```typescript
// lib/navigation.ts
export interface NavItem {
  label: string;
  href: string;
  icon: string;
  roles: string[];
}

export const NAV_ITEMS: NavItem[] = [
  { label: 'POS',           href: '/pos',                    icon: 'ShoppingCart', roles: ['cashier', 'attendant'] },
  { label: 'Sales',         href: '/dashboard/sales',        icon: 'BarChart',     roles: ['manager', 'admin', 'accountant'] },
  { label: 'Inventory',     href: '/dashboard/inventory',    icon: 'Package',      roles: ['manager', 'admin'] },
  { label: 'Finance',       href: '/dashboard/finance',      icon: 'BookOpen',     roles: ['accountant', 'admin'] },
  { label: 'HR',            href: '/dashboard/hr',           icon: 'Users',        roles: ['manager', 'admin'] },
  { label: 'Fuel',          href: '/dashboard/fuel',         icon: 'Fuel',         roles: ['manager', 'admin'] },
  { label: 'Approvals',     href: '/dashboard/approvals',    icon: 'CheckSquare',  roles: ['manager', 'admin', 'accountant'] },
  { label: 'Assets',        href: '/dashboard/assets',       icon: 'Layers',       roles: ['accountant', 'admin'] },
  { label: 'Users',         href: '/dashboard/users',        icon: 'UserCog',      roles: ['admin'] },
  { label: 'System Config', href: '/dashboard/config',       icon: 'Settings',     roles: ['admin'] },
];
```

Filter in the Sidebar component using the role from Zustand. Also protect routes in `middleware.ts` — UI hiding alone is not security.

---

## Offline & Sync

### 4. Sync Status Banner (POS)

**Problem**: TanStack Query assumes connectivity. There is currently no offline handling. A cashier on a tablet that loses connection mid-shift will have no idea if transactions are saved.

**Immediate action**: Add a `SyncStatusBanner` component to the POS layout. It must always be visible.

```typescript
// components/pos/SyncStatusBanner.tsx
'use client';
import { useEffect, useState } from 'react';

export function SyncStatusBanner() {
  const [online, setOnline] = useState(true);
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    const handleOnline  = () => setOnline(true);
    const handleOffline = () => setOnline(false);
    window.addEventListener('online',  handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online',  handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Read pending count from localStorage queue
  // ...

  if (online && pendingCount === 0) return null;

  return (
    <div className={`px-4 py-2 text-sm font-medium ${online ? 'bg-yellow-500' : 'bg-red-600'} text-white`}>
      {online
        ? `${pendingCount} transaction(s) syncing…`
        : `Offline — ${pendingCount} transaction(s) pending sync`}
    </div>
  );
}
```

### 5. Offline Queue

Build `lib/offlineQueue.ts` to persist sales that cannot be submitted immediately.

```typescript
// lib/offlineQueue.ts
interface PendingOperation {
  id: string;           // deterministic UUID (crypto.randomUUID())
  type: 'sale' | 'stock_adjustment';
  payload: unknown;
  createdAt: string;    // ISO 8601
  attempts: number;
  status: 'pending' | 'syncing' | 'confirmed' | 'failed';
}

const QUEUE_KEY = 'nexus_offline_queue';

export function enqueue(op: Omit<PendingOperation, 'id' | 'createdAt' | 'attempts' | 'status'>): PendingOperation {
  const item: PendingOperation = {
    ...op,
    id: crypto.randomUUID(),
    createdAt: new Date().toISOString(),
    attempts: 0,
    status: 'pending',
  };
  const queue = getQueue();
  queue.push(item);
  localStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
  return item;
}

export function getQueue(): PendingOperation[] {
  return JSON.parse(localStorage.getItem(QUEUE_KEY) ?? '[]');
}

export function markConfirmed(id: string): void { /* update status in localStorage */ }
export function markFailed(id: string):    void { /* update status, increment attempts */ }
```

On reconnect (listen to `window.addEventListener('online', ...)`), drain the queue by replaying each operation against the API.

### 6. Cart Persistence

POS sale forms must survive network loss and accidental page reload.

- Auto-save cart contents to localStorage every 30 seconds
- On POS mount: check for a saved cart and show a "Restore previous cart?" prompt if one exists
- Never clear the form on a failed submission — show error state with retry button
- Show "X items in saved cart" in the POS header

---

## Session Management

### 7. Offline-Aware 401 Handling

Current behaviour: any 401 response redirects to `/login`. This breaks for cashiers who are offline but have a valid in-memory session.

Extend `lib/api.ts`:

```typescript
// In the fetch wrapper's error handler:
if (response.status === 401) {
  if (!navigator.onLine) {
    // Do NOT redirect — session may be fine, we just cannot verify it
    // Queue the request; show "Session will refresh when online"
    return;
  }
  // Attempt token refresh
  const refreshed = await attemptRefresh();
  if (refreshed) {
    return retry(request);
  }
  // Refresh truly failed (account deactivated etc.)
  router.push('/login');
}
```

Also add a session expiry warning in the POS layout: if the access token expires in under 10 minutes, show a non-blocking banner. Refresh silently in the background; only surface to the user if refresh fails.

---

## Receipt & Printing

### 8. Receipt Component

Build `components/pos/Receipt.tsx` targeting 58mm thermal paper format.

Receipt must include:
- FDN number from EFRIS (show "PENDING TAX REGISTRATION" watermark if not yet confirmed)
- QR code (use `qrcode.react`)
- Line items with quantities and prices
- Subtotal, tax (VAT/EFRIS), and total
- Payment method and amount tendered / change given
- Cashier name, outlet name, date/time, shift ID

Print via `window.print()`. Add the following to `app/(pos)/pos/receipt/print.css` (import in the receipt page):

```css
@media print {
  body * { visibility: hidden; }
  #receipt-printable,
  #receipt-printable * { visibility: visible; }
  #receipt-printable {
    position: fixed;
    top: 0;
    left: 0;
    width: 58mm;
    font-size: 10pt;
    font-family: monospace;
    line-height: 1.4;
  }
}
```

Always provide a "Download as PDF" button as a fallback (`window.print()` to PDF works in all modern browsers).

For Bluetooth thermal printers: use `react-thermal-printer` (Web Bluetooth API). This is progressive enhancement — the print button must work without Bluetooth.

EFRIS pending flow: if the receipt is printed before the FDN is received, allow the cashier to reprint from the sale detail page once the FDN is confirmed. Provide a "Reprint Receipt" button on the sale detail page.

---

## Barcode Scanning

### 9. Scanner Support

USB and Bluetooth barcode scanners present as keyboard emulators. When the POS is active, the product search input must be auto-focused so scanner output populates it without any extra interaction. This works with no additional code as long as:

```typescript
// In the POS sale page, ensure search input is focused on mount
useEffect(() => {
  searchInputRef.current?.focus();
}, []);
```

For camera-based scanning (tablet fallback): integrate `react-zxing`. Add a scan icon button beside the search input that activates the camera scanner. Camera scanning is secondary — scanner-as-keyboard is the primary path.

---

## Modules to Build

### 10. Finance Module (`/dashboard/finance/`)

Screens needed:
- Chart of accounts (tree view, add/edit accounts)
- Journal entry list + create form (debit/credit rows, must balance before submit)
- Trial balance report (date range filter, export to PDF)
- Cash requisitions list + approve/reject (links into Approvals workflow)
- Bank reconciliation (match statement lines to GL entries)

Key endpoints (verify in Swagger before building):
```
GET    /api/accounts/
POST   /api/accounts/
GET    /api/journal-entries/
POST   /api/journal-entries/
GET    /api/reports/trial-balance/
GET    /api/cash-requisitions/
POST   /api/cash-requisitions/{id}/approve/
```

### 11. HR Module (`/dashboard/hr/`)

Screens needed:
- Employee list + profile (personal details, employment info, outlet assignment)
- Leave requests (submit, list, approve/reject by manager)
- Attendance log (clock-in/out view per employee per day)
- Payroll runs (list, generate, approve, export payslips)

Key endpoints:
```
GET    /api/employees/
POST   /api/employees/
GET    /api/leave-requests/
POST   /api/leave-requests/
POST   /api/leave-requests/{id}/approve/
GET    /api/attendance/
GET    /api/payroll/
POST   /api/payroll/generate/
```

### 12. Inventory Module (`/dashboard/inventory/`)

Screens needed:
- Supplier list + create/edit
- Purchase orders (create, receive goods, list with status)
- Stock transfers between outlets
- Stock audit log (read-only, filterable by product/outlet/date)

Key endpoints:
```
GET    /api/suppliers/
GET    /api/purchase-orders/
POST   /api/purchase-orders/
POST   /api/purchase-orders/{id}/receive/
GET    /api/stock-transfers/
POST   /api/stock-transfers/
GET    /api/stock-audit/
```

### 13. Approvals Module (`/dashboard/approvals/`)

Approval workflows power leave requests, cash requisitions, purchase orders, and payroll. The UI must:
- Show a unified pending approvals inbox (all types in one list, filterable by type)
- Show approval history with who approved/rejected at each level
- Allow approve/reject with a required comment field
- Show the multi-level chain (e.g., Manager → Director → CFO) and which step is current

Key endpoints:
```
GET    /api/approvals/                         # pending items for current user
GET    /api/approvals/?status=all             # full history
POST   /api/approvals/{id}/approve/
POST   /api/approvals/{id}/reject/
```

### 14. Assets Module (`/dashboard/assets/`)

Screens needed:
- Asset list (filter by category, location, status)
- Asset detail (purchase date, cost, accumulated depreciation, current book value)
- Depreciation schedule (table showing monthly depreciation over asset life)
- Asset disposal form

Key endpoints:
```
GET    /api/assets/
POST   /api/assets/
GET    /api/assets/{id}/
GET    /api/assets/{id}/depreciation/
POST   /api/assets/{id}/dispose/
```

### 15. Fuel Module (`/dashboard/fuel/`)

Screens needed:
- Pump list per outlet (pump number, product, current reading)
- Tank levels (dip readings, low stock alert threshold)
- Daily reconciliation form (opening reading, closing reading, meter sales vs cash sales)
- Reconciliation history

### 16. Phase 8 Modules (Build When Backend Is Ready)

Coordinate with the backend developer before starting — Phase 8 stubs exist but endpoints are not fully implemented.

**Café (`/dashboard/cafe/`)**:
- Menu item management (with category, price, image)
- Recipe viewer (ingredients and quantities per item)
- Order management (dine-in vs takeaway tabs)
- Waste logging form

**Projects (`/dashboard/projects/`)**:
- Project list and create
- Kanban task board per project
- Time entry log
- Budget vs actual bar chart

**Manufacturing (`/dashboard/manufacturing/`)**:
- Production order list and create
- Bill of materials editor (nested tree)
- Work-in-progress tracker
- Finished goods entry form

---

## API Integration Checklist

Before building each screen, confirm the endpoint exists and returns the expected shape in Swagger at `/api/docs/`.

- [ ] `POST /api/checkout/` — process a sale
- [ ] `GET  /api/sales/` — sale history (paginated)
- [ ] `GET  /api/sales/{id}/` — sale detail with items and payments
- [ ] `GET  /api/sales/{id}/receipt/` — receipt data including FDN
- [ ] `POST /api/sales/{id}/void/` — void a sale
- [ ] `GET  /api/shifts/my_current/` — current user's open shift
- [ ] `POST /api/shifts/open/` — open a shift
- [ ] `POST /api/shifts/{id}/close/` — close a shift with reconciliation data
- [ ] `GET  /api/accounts/` — chart of accounts
- [ ] `POST /api/journal-entries/` — create journal entry
- [ ] `GET  /api/reports/trial-balance/` — trial balance (accepts date range params)
- [ ] `GET  /api/employees/` — employee list
- [ ] `POST /api/leave-requests/` — submit leave request
- [ ] `GET  /api/payroll/` — payroll runs
- [ ] `GET  /api/purchase-orders/` — purchase order list
- [ ] `POST /api/stock-transfers/` — initiate stock transfer
- [ ] `GET  /api/approvals/` — pending approvals for current user
- [ ] `POST /api/approvals/{id}/approve/` — approve an item
- [ ] `GET  /api/assets/` — asset list
- [ ] `GET  /api/assets/{id}/depreciation/` — depreciation schedule
- [ ] `GET  /api/notifications/` — notification list
- [ ] `POST /api/notifications/{id}/read/` — mark notification read

---

## Priority Order

Build in this sequence. Each item is blocked on the previous only where noted.

| # | Task | Estimate | Depends on |
|---|------|----------|------------|
| 1 | Role-based dashboard routing + middleware | 1 day | — |
| 2 | POS layout group (separate from dashboard) | 1 day | — |
| 3 | Shift open/close UI | 1 day | 2 |
| 4 | POS checkout screen (product grid + cart + calculator) | 3 days | 2, 3 |
| 5 | Receipt component + print CSS | 1 day | 4 |
| 6 | Sync status banner + offline queue | 2 days | 2 |
| 7 | Cart persistence (localStorage) | 0.5 days | 4 |
| 8 | Role-filtered navigation + route guards | 1 day | 1 |
| 9 | Finance module UI | 3 days | — |
| 10 | HR module UI | 3 days | — |
| 11 | Inventory module UI | 2 days | — |
| 12 | Approvals UI | 2 days | — |
| 13 | Assets module UI | 1.5 days | — |
| 14 | Fuel module UI | 2 days | — |
| 15 | Phase 8 modules | 5 days | Backend ready |

**Total estimate**: ~3.5 weeks for full frontend integration.

---

## Common API Patterns

### TanStack Query hooks

```typescript
// lib/hooks/useSales.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';

export function useSales(params?: { page?: number; outlet?: number }) {
  return useQuery({
    queryKey: ['sales', params],
    queryFn: () => apiClient('/sales/', { params }),
  });
}

export function useCheckout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CheckoutPayload) =>
      apiClient('/checkout/', { method: 'POST', body: JSON.stringify(payload) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sales'] });
      queryClient.invalidateQueries({ queryKey: ['shifts'] });
    },
  });
}
```

### Paginated list response shape

```typescript
interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
```

### Error response shape

```typescript
interface APIError {
  error: string;
  detail?: string;
}
```

Handle 400 errors by displaying `error` to the user. Log `detail` to the console in development.

---

## Dev Setup

```bash
# Backend (Docker)
docker compose up

# Frontend
cd frontend
pnpm install        # if not already installed
pnpm dev            # runs on http://localhost:3000

# API base URL in .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Swagger UI: `http://localhost:8000/api/docs/`  
Admin panel: `http://localhost:8000/admin/`

The backend runs behind django-tenants. All tenant-scoped API calls require the `Host` header to match a registered tenant domain. In development, `localhost` is mapped to the demo tenant. If you see 404s on tenant-scoped endpoints, confirm the demo tenant exists:

```bash
docker compose exec backend python manage.py create_tenant \
  --schema_name demo --name "Demo Business" \
  --domain-domain "localhost" --domain-is_primary True
```

---

## Phase 6 — Payments Integration

### Payment Configuration (`/dashboard/settings/payments`)
Admin page to configure credentials for payment providers.

- **Endpoint**: `GET/PATCH /api/payments/config/`
- **Security**: Secrets are write-only — they will not be returned by the API once saved.

### Initiating a Collection (Customer Pays Business)
**Endpoint**: `POST /api/payments/initiate/`

```typescript
interface InitiatePaymentRequest {
  amount: string;            // e.g. "50000.00" — always a string, never float
  method: 'mobile_money' | 'card' | 'bank';
  provider?: 'mtn' | 'airtel' | 'pesapal' | 'mock';
  phone_number?: string;     // Required for mobile_money
  customer_email?: string;
  customer_name?: string;
  description?: string;
  sale_id?: number;
}
```

### Initiating a Disbursement (Business Pays Out)
**Endpoint**: `POST /api/payments/disburse/`

```typescript
interface InitiateDisbursementRequest {
  amount: string;
  method: 'mobile_money';
  provider?: 'mtn' | 'airtel' | 'mock';
  phone_number: string;
  customer_name?: string;
  description?: string;
}
```

### Polling Payment Status
**Endpoint**: `POST /api/payments/transactions/{id}/refresh_status/`

Returns the updated `PaymentTransaction`. Poll until `is_terminal` is `true`, then check `status`.

```typescript
interface PaymentTransaction {
  id: number;
  transaction_type: 'collection' | 'disbursement';
  provider: 'mock' | 'mtn' | 'airtel' | 'pesapal';
  status: 'pending' | 'processing' | 'success' | 'failed' | 'cancelled' | 'expired';
  is_terminal: boolean;
  amount: string;
  currency: string;
  phone_number: string;
  reference: string;
  provider_transaction_id: string;
  error_message: string;
  created_at: string;
}
```

---

## Role-Based Permissions Endpoint

Fetch immediately after login and store in Zustand. Use to gate sidebar items and action buttons.

**Endpoint**: `GET /api/auth/me/permissions/`

```json
{
  "role": "cashier",
  "sections": ["dashboard", "pos", "sales", "shifts", "products", "fuel", "notifications"],
  "actions": ["open_shift", "close_shift", "process_sale"]
}
```

- **Sidebar**: Only render items whose key is in `sections`.
- **Buttons**: Only render action buttons (e.g., "Void Sale") if the action is in `actions`.
- Do not rely on role string alone — always check the `sections`/`actions` arrays.

---

## Platform Admin Dashboard

Separate UI for Kakebe Technologies staff to manage all business tenants. This is **not** the per-tenant admin — it is a cross-tenant management panel.

Key views:
- List all businesses/tenants with subscription status
- Create new tenant (triggers schema provisioning + welcome email)
- Suspend / reactivate tenant
- Cross-tenant analytics (aggregate sales, active users)

This panel lives at a separate subdomain or path and uses admin-scoped JWT tokens.
