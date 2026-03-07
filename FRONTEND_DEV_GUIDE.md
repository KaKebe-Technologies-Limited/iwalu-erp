# Frontend Developer Guide — Phase 3 Changes

**Date**: March 2026
**Context**: Phase 3 (POS & Sales) backend is complete. This guide covers what the frontend needs to integrate.

---

## 1. Pagination Migration

All list endpoints now return paginated responses. Your API client and hooks need to handle this.

### Old format (flat array)
```json
[{ "id": 1, "name": "..." }, { "id": 2, "name": "..." }]
```

### New format (paginated)
```json
{
  "count": 42,
  "next": "http://localhost:8000/api/users/?page=2",
  "previous": null,
  "results": [{ "id": 1, "name": "..." }, { "id": 2, "name": "..." }]
}
```

### What to change

**TanStack Query hooks** — extract `.results` for list data:
```typescript
// lib/hooks/useUsers.ts
export function useUsers(search = '', page = 1) {
  return useQuery({
    queryKey: ['users', search, page],
    queryFn: () => apiClient(`/users/?search=${search}&page=${page}`),
    select: (data) => data, // full response — use data.results for items, data.count for total
  });
}
```

**Components** — access `data.results` instead of `data` directly:
```typescript
const { data } = useUsers();
// Before: data.map(...)
// After:  data?.results.map(...)
// Total:  data?.count
// Next:   data?.next
```

**Affected files**: Any component that calls a list endpoint (users, outlets, products, categories, sales, shifts, discounts).

### Pagination TypeScript interface
```typescript
interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
```

---

## 2. Social Login Integration

Backend now supports Google and Apple sign-in.

### Flow
1. User clicks "Sign in with Google" button
2. Frontend uses Google Identity Services JS SDK to get an `access_token`
3. Frontend sends token to backend: `POST /api/auth/social/google/`
4. Backend verifies with Google, creates/links user, returns JWT tokens
5. Store tokens in Zustand auth store — same as regular login

### Google Setup
```typescript
// Install: npm install @react-oauth/google

// In your app provider (layout.tsx or providers.tsx):
import { GoogleOAuthProvider } from '@react-oauth/google';

<GoogleOAuthProvider clientId={process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID!}>
  {children}
</GoogleOAuthProvider>

// In login page:
import { useGoogleLogin } from '@react-oauth/google';

const googleLogin = useGoogleLogin({
  onSuccess: async (tokenResponse) => {
    const res = await apiClient('/auth/social/google/', {
      method: 'POST',
      body: JSON.stringify({ access_token: tokenResponse.access_token }),
    });
    // res contains { access, refresh, user }
    // Store in auth store
  },
});
```

### Apple Setup
```typescript
// Apple Sign-In uses the Apple JS SDK
// POST /api/auth/social/apple/ with { access_token, id_token }
```

### Backend endpoints
```
POST /api/auth/social/google/    → { access_token: "..." } → { access, refresh, user }
POST /api/auth/social/apple/     → { access_token: "...", id_token: "..." } → { access, refresh, user }
```

---

## 3. New POS Pages to Build

### 3.1 Outlets Management (`/dashboard/outlets`)
- Table: name, type, address, phone, active status
- Create/Edit modal
- Filter by outlet type
- Admin/Manager only for write operations

### 3.2 Products & Categories (`/dashboard/products`)
- **Categories tab**: tree view or flat list, filter by business_unit
- **Products tab**: table with search by name/sku/barcode, filter by category
- Low stock indicator (products at/below reorder level)
- Stock adjustment modal (admin/manager only)
- Create/Edit modals for both

### 3.3 POS Checkout (`/dashboard/pos`)
The core sales interface for cashiers.

**Layout**: Product grid/search on left, cart on right

**Flow**:
1. Cashier opens shift → `POST /api/shifts/open/` with outlet + opening cash
2. Search/scan products → add to cart
3. Apply discounts (item-level or sale-level)
4. Enter payments (cash/mobile money/card/bank — can split)
5. Submit → `POST /api/checkout/`
6. Show receipt → `GET /api/sales/{id}/receipt/`
7. End of day → `POST /api/shifts/{id}/close/` with cash count

**Checkout payload**:
```typescript
interface CheckoutRequest {
  items: Array<{
    product_id: number;
    quantity: number;   // decimal string: "10.000"
    discount_id?: number;
  }>;
  payments: Array<{
    payment_method: 'cash' | 'bank' | 'mobile_money' | 'card';
    amount: number;     // decimal string: "53100.00"
    reference?: string; // for mobile money / bank transfers
  }>;
  discount_id?: number; // sale-level discount
  notes?: string;
}
```

### 3.4 Shift Management (`/dashboard/shifts`)
- Open/close shift UI
- Current shift status indicator
- Shift history with cash reconciliation

### 3.5 Sales History (`/dashboard/sales`)
- Table: receipt #, outlet, total, status, date
- Search by receipt number
- Filter by outlet, status, shift
- Detail view with items + payments
- Void button (admin/manager only)
- Receipt print/view

### 3.6 Discounts (`/dashboard/discounts`)
- Table: name, type, value, active, valid dates
- Create/Edit modal
- Admin/Manager only for write

---

## 4. API Reference — New Endpoints

### Outlets
```
GET    /api/outlets/                     → paginated list (filter: outlet_type, is_active; search: name, address)
POST   /api/outlets/                     → create (admin/manager)
GET    /api/outlets/{id}/                → retrieve
PATCH  /api/outlets/{id}/                → update (admin/manager)
DELETE /api/outlets/{id}/                → delete (admin/manager)
```

### Categories
```
GET    /api/categories/                  → paginated list (filter: business_unit, parent, is_active)
POST   /api/categories/                  → create (admin/manager)
GET    /api/categories/{id}/             → retrieve
PATCH  /api/categories/{id}/             → update (admin/manager)
DELETE /api/categories/{id}/             → delete (admin/manager)
```

### Products
```
GET    /api/products/                    → paginated list (search: name, sku, barcode; filter: category, is_active)
POST   /api/products/                    → create (admin/manager)
GET    /api/products/{id}/               → retrieve
PATCH  /api/products/{id}/               → update (admin/manager)
DELETE /api/products/{id}/               → delete (admin/manager)
GET    /api/products/low_stock/          → products at/below reorder level
POST   /api/products/{id}/adjust_stock/  → { quantity: "50.000", reason: "Delivery" } (admin/manager)
```

### Shifts
```
GET    /api/shifts/                      → paginated list (filter: outlet, status)
POST   /api/shifts/open/                 → open shift { outlet: 1, opening_cash: "50000.00" }
POST   /api/shifts/{id}/close/           → close shift { closing_cash: "103000.00", notes: "" }
GET    /api/shifts/my_current/           → current user's open shift
```

### Checkout & Sales
```
POST   /api/checkout/                    → process sale (see payload above)
GET    /api/sales/                       → paginated list (search: receipt_number; filter: outlet, status, shift)
GET    /api/sales/{id}/                  → detail with items + payments
POST   /api/sales/{id}/void/             → void sale, restore stock (admin/manager)
GET    /api/sales/{id}/receipt/          → receipt data
```

### Discounts
```
GET    /api/discounts/                   → paginated list (filter: discount_type, is_active)
POST   /api/discounts/                   → create (admin/manager)
GET    /api/discounts/{id}/              → retrieve
PATCH  /api/discounts/{id}/              → update (admin/manager)
DELETE /api/discounts/{id}/              → delete (admin/manager)
```

---

## 5. Platform Admin Dashboard (Future Phase — Spec Only)

This is for Kakebe Technologies to manage tenants/businesses.

### Concept
- Separate route: `/platform-admin`
- Protected by `superuser` check (or a future `is_platform_admin` flag)
- Uses shared-schema API endpoints (to be built in a future phase)

### Key views (planning only)
- List all businesses/tenants
- Create new tenant (provision schema)
- Suspend/activate tenant
- Cross-tenant analytics (revenue, active users)

**No backend endpoints for this yet** — this section is for planning the frontend shell/layout only.

---

## 6. TypeScript Interfaces

```typescript
interface Outlet {
  id: number;
  name: string;
  outlet_type: 'fuel_station' | 'cafe' | 'supermarket' | 'boutique' | 'bridal' | 'general';
  address: string;
  phone: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface Category {
  id: number;
  name: string;
  business_unit: 'fuel' | 'cafe' | 'supermarket' | 'boutique' | 'bridal' | 'general';
  description: string;
  parent: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface Product {
  id: number;
  name: string;
  sku: string;
  barcode: string;
  category: number;
  category_name: string;
  cost_price: string;
  selling_price: string;
  tax_rate: string;
  track_stock: boolean;
  stock_quantity: string;
  reorder_level: string;
  unit: 'piece' | 'litre' | 'kg' | 'metre' | 'box' | 'pack';
  is_active: boolean;
  is_low_stock: boolean;
  created_at: string;
  updated_at: string;
}

interface Discount {
  id: number;
  name: string;
  discount_type: 'percentage' | 'fixed';
  value: string;
  is_active: boolean;
  valid_from: string | null;
  valid_until: string | null;
  created_at: string;
  updated_at: string;
}

interface Shift {
  id: number;
  outlet: number;
  user_id: number;
  status: 'open' | 'closed';
  opening_cash: string;
  closing_cash: string | null;
  expected_cash: string | null;
  notes: string;
  opened_at: string;
  closed_at: string | null;
}

interface Sale {
  id: number;
  receipt_number: string;
  outlet: number;
  shift: number;
  cashier_id: number;
  subtotal: string;
  tax_total: string;
  discount_total: string;
  grand_total: string;
  discount: number | null;
  status: 'completed' | 'voided' | 'refunded';
  notes: string;
  items: SaleItem[];
  payments: SalePayment[];
  created_at: string;
  updated_at: string;
}

interface SaleItem {
  id: number;
  product: number;
  product_name: string;
  unit_price: string;
  quantity: string;
  tax_rate: string;
  tax_amount: string;
  discount: number | null;
  discount_amount: string;
  line_total: string;
}

interface SalePayment {
  id: number;
  payment_method: 'cash' | 'bank' | 'mobile_money' | 'card';
  amount: string;
  reference: string;
  created_at: string;
}
```

---

## 7. Sidebar Navigation Updates

Add these items to the sidebar (after Users):

```
Outlets        → /dashboard/outlets
Products       → /dashboard/products
POS            → /dashboard/pos
Sales          → /dashboard/sales
Shifts         → /dashboard/shifts
Discounts      → /dashboard/discounts
```

Group suggestion:
- **Management**: Users, Outlets
- **Inventory**: Products (includes Categories)
- **Sales**: POS, Sales History, Shifts, Discounts
