# Phase 4 Implementation Plan: Inventory Management & Reporting (Frontend Integration)

## Discovery Summary

**Backend status: 100% complete.** All APIs are live and functional:
- `inventory/` app: Suppliers, OutletStock, PurchaseOrders, StockTransfers, StockAuditLog
- `reports/` app: 9 aggregation endpoints + consolidated dashboard

**Frontend status: 0% integrated.** All 5 target pages use hardcoded mock data. No TanStack Query hooks exist for inventory or reports.

**Work is entirely frontend:**
1. Add TypeScript interfaces for inventory + report response types
2. Create hooks for inventory (5 endpoints) and reports (9 endpoints)
3. Wire inventory page, reports page, main dashboard, employees page

---

## Allowed API Reference

### Inventory Endpoints
```
GET/POST   /api/suppliers/                           → CRUD suppliers
PATCH/DEL  /api/suppliers/{id}/                      → Update/delete supplier

GET        /api/outlet-stock/                        → List outlet stock (read-only)
GET        /api/outlet-stock/low/                    → Below reorder level

GET/POST   /api/purchase-orders/                     → List / create PO
GET        /api/purchase-orders/{id}/                → PO detail with items
POST       /api/purchase-orders/{id}/submit/         → Submit draft PO
POST       /api/purchase-orders/{id}/receive/        → Receive PO (body: {items: [{id, quantity_received}]})
POST       /api/purchase-orders/{id}/cancel/         → Cancel PO

GET/POST   /api/stock-transfers/                     → List / create transfer
GET        /api/stock-transfers/{id}/                → Transfer detail with items
POST       /api/stock-transfers/{id}/dispatch/       → Mark in transit
POST       /api/stock-transfers/{id}/receive/        → Mark received
POST       /api/stock-transfers/{id}/cancel/         → Cancel transfer

GET        /api/stock-audit-log/                     → Audit log (read-only, filters: product, outlet, movement_type)
```

### Create Request Bodies (CRITICAL — use _id suffix, not FK name)
```json
// POST /api/purchase-orders/
{ "supplier_id": 1, "outlet_id": 1, "expected_date": "2026-04-01", "notes": "", "items": [{"product_id": 1, "quantity_ordered": "10.000", "unit_cost": "5000.00"}] }

// POST /api/stock-transfers/
{ "from_outlet_id": 1, "to_outlet_id": 2, "notes": "", "items": [{"product_id": 1, "quantity": "5.000"}] }

// POST /api/purchase-orders/{id}/receive/
{ "items": [{"id": 1, "quantity_received": "10.000"}] }
```

### Reports Endpoints
```
GET  /api/reports/dashboard/                         → Today KPIs (all auth users)
GET  /api/reports/sales-summary/?date_from=&date_to=&outlet=
GET  /api/reports/sales-by-outlet/?date_from=&date_to=
GET  /api/reports/sales-by-product/?date_from=&date_to=&category=
GET  /api/reports/sales-by-payment-method/?date_from=&date_to=
GET  /api/reports/hourly-sales/?date=&outlet=
GET  /api/reports/stock-levels/?outlet=&low_stock=true
GET  /api/reports/stock-movement/?date_from=&date_to=&product=&movement_type=
GET  /api/reports/shift-summary/?date_from=&date_to=&outlet=&user_id=
```

### Users Endpoints
```
GET    /api/users/                    → List (search, is_active filter)
POST   /api/users/                    → Create
PATCH  /api/users/{id}/               → Update
POST   /api/users/{id}/deactivate/    → Deactivate
POST   /api/users/{id}/activate/      → Activate
```

### Anti-Patterns — DO NOT DO THESE
- Do NOT use `supplier`, `outlet` (without `_id`) in create/update POST bodies
- Do NOT call DELETE on `/api/outlet-stock/` — it's read-only
- Do NOT call DELETE on `/api/stock-audit-log/` — it's read-only
- Do NOT invent endpoints like `/api/reports/export/` — does not exist
- Do NOT add `accounting/` endpoints — not built in backend
- Do NOT use `from_outlet`/`to_outlet` in transfer create — use `from_outlet_id`/`to_outlet_id`

---

## Phase 1: TypeScript Interfaces

**File**: `frontend/src/lib/types.ts`
**Action**: Append new interfaces to the end of the existing file
**Copy pattern**: Match style of existing `Product`, `Sale` interfaces — FK IDs as `number`, decimals as `string`, nested read-only names included

### Interfaces to Add

```typescript
// ─── Inventory ───────────────────────────────────────────────────────────────

export interface Supplier {
  id: number;
  name: string;
  contact_person: string;
  email: string;
  phone: string;
  address: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface OutletStock {
  id: number;
  product: number;
  product_name: string;
  product_sku: string;
  outlet: number;
  outlet_name: string;
  quantity: string;
  updated_at: string;
}

export interface PurchaseOrderItem {
  id: number;
  product: number;
  product_name: string;
  quantity_ordered: string;
  quantity_received: string;
  unit_cost: string;
  line_total: string;
}

export interface PurchaseOrder {
  id: number;
  po_number: string;
  supplier: number;
  supplier_name: string;
  outlet: number;
  outlet_name: string;
  ordered_by: number;
  status: 'draft' | 'submitted' | 'partial' | 'received' | 'cancelled';
  expected_date: string | null;
  total_cost: string;
  notes: string;
  items: PurchaseOrderItem[];
  created_at: string;
  updated_at: string;
}

export interface PurchaseOrderCreate {
  supplier_id: number;
  outlet_id: number;
  expected_date?: string;
  notes?: string;
  items: Array<{
    product_id: number;
    quantity_ordered: string;
    unit_cost: string;
  }>;
}

export interface StockTransferItem {
  id: number;
  product: number;
  product_name: string;
  quantity: string;
  quantity_received: string;
}

export interface StockTransfer {
  id: number;
  transfer_number: string;
  from_outlet: number;
  from_outlet_name: string;
  to_outlet: number;
  to_outlet_name: string;
  initiated_by: number;
  status: 'pending' | 'in_transit' | 'completed' | 'cancelled';
  notes: string;
  items: StockTransferItem[];
  created_at: string;
  updated_at: string;
}

export interface StockTransferCreate {
  from_outlet_id: number;
  to_outlet_id: number;
  notes?: string;
  items: Array<{
    product_id: number;
    quantity: string;
  }>;
}

export interface StockAuditLog {
  id: number;
  product: number;
  product_name: string;
  outlet: number | null;
  outlet_name: string | null;
  movement_type: 'sale' | 'void' | 'adjustment' | 'transfer_out' | 'transfer_in' | 'purchase';
  movement_type_display: string;
  quantity_change: string;
  quantity_before: string;
  quantity_after: string;
  reference_type: string;
  reference_id: number | null;
  user_id: number;
  notes: string;
  created_at: string;
}

// ─── Reports ─────────────────────────────────────────────────────────────────

export interface DashboardData {
  today_revenue: string;
  today_sales_count: number;
  today_items_sold: string;
  low_stock_count: number;
  open_shifts: number;
  payment_method_breakdown: Array<{
    payment_method: string;
    total: string;
    count: number;
  }>;
  recent_sales: Sale[];
}

export interface SalesSummary {
  date_from: string | null;
  date_to: string | null;
  total_sales: number;
  total_revenue: string;
  total_tax: string;
  total_discounts: string;
  average_sale: string;
}

export interface SalesByOutlet {
  outlet_id: number;
  outlet_name: string;
  total_sales: number;
  total_revenue: string;
}

export interface SalesByProduct {
  product_id: number;
  product_name: string;
  sku: string;
  total_quantity: string;
  total_revenue: string;
}

export interface SalesByPaymentMethod {
  payment_method: string;
  total_amount: string;
  count: number;
}

export interface HourlySales {
  hour: string;
  total_sales: number;
  total_revenue: string;
}

export interface StockLevel {
  product_id: number;
  product_name: string;
  sku: string;
  outlet_id: number | null;
  outlet_name: string | null;
  quantity: string;
  reorder_level: string;
  is_low_stock: boolean;
}

export interface ShiftSummaryReport {
  shift_id: number;
  outlet_name: string;
  cashier_name: string;
  opened_at: string;
  closed_at: string | null;
  status: string;
  sales_count: number;
  total_revenue: string;
  opening_cash: string;
  closing_cash: string | null;
}
```

**Verification checklist**:
- [ ] `grep 'Supplier' frontend/src/lib/types.ts` → finds `export interface Supplier`
- [ ] `grep 'PurchaseOrder' frontend/src/lib/types.ts` → finds all 3 PO interfaces
- [ ] `grep 'StockAuditLog' frontend/src/lib/types.ts` → finds interface
- [ ] `grep 'DashboardData' frontend/src/lib/types.ts` → finds interface

---

## Phase 2: Inventory Hooks

**File**: `frontend/src/lib/hooks/useInventory.ts` (create new file)
**Copy pattern from**: `frontend/src/lib/hooks/useProducts.ts` (lines 1-59)

```typescript
'use client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api';
import type {
  PaginatedResponse,
  Supplier,
  OutletStock,
  PurchaseOrder,
  PurchaseOrderCreate,
  StockTransfer,
  StockTransferCreate,
  StockAuditLog,
} from '../types';

// ─── Suppliers ───────────────────────────────────────────────────────────────

export function useSuppliers(params: { search?: string; is_active?: boolean; page?: number } = {}) {
  return useQuery<PaginatedResponse<Supplier>>({
    queryKey: ['suppliers', params],
    queryFn: () => {
      const query = new URLSearchParams();
      if (params.search) query.append('search', params.search);
      if (params.is_active !== undefined) query.append('is_active', String(params.is_active));
      if (params.page) query.append('page', String(params.page));
      return apiClient(`/suppliers/?${query.toString()}`);
    },
  });
}

export function useCreateSupplier() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Supplier>) =>
      apiClient('/suppliers/', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['suppliers'] }),
  });
}

export function useUpdateSupplier() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: Partial<Supplier> & { id: number }) =>
      apiClient(`/suppliers/${id}/`, { method: 'PATCH', body: JSON.stringify(data) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['suppliers'] }),
  });
}

export function useDeleteSupplier() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiClient(`/suppliers/${id}/`, { method: 'DELETE' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['suppliers'] }),
  });
}

// ─── Outlet Stock ─────────────────────────────────────────────────────────────

export function useOutletStock(params: { outlet?: number; product?: number; page?: number } = {}) {
  return useQuery<PaginatedResponse<OutletStock>>({
    queryKey: ['outlet-stock', params],
    queryFn: () => {
      const query = new URLSearchParams();
      if (params.outlet) query.append('outlet', String(params.outlet));
      if (params.product) query.append('product', String(params.product));
      if (params.page) query.append('page', String(params.page));
      return apiClient(`/outlet-stock/?${query.toString()}`);
    },
  });
}

export function useLowOutletStock() {
  return useQuery<PaginatedResponse<OutletStock>>({
    queryKey: ['outlet-stock', 'low'],
    queryFn: () => apiClient('/outlet-stock/low/'),
  });
}

// ─── Purchase Orders ──────────────────────────────────────────────────────────

export function usePurchaseOrders(params: { status?: string; outlet?: number; page?: number } = {}) {
  return useQuery<PaginatedResponse<PurchaseOrder>>({
    queryKey: ['purchase-orders', params],
    queryFn: () => {
      const query = new URLSearchParams();
      if (params.status) query.append('status', params.status);
      if (params.outlet) query.append('outlet', String(params.outlet));
      if (params.page) query.append('page', String(params.page));
      return apiClient(`/purchase-orders/?${query.toString()}`);
    },
  });
}

export function usePurchaseOrder(id: number) {
  return useQuery<PurchaseOrder>({
    queryKey: ['purchase-orders', id],
    queryFn: () => apiClient(`/purchase-orders/${id}/`),
    enabled: !!id,
  });
}

export function useCreatePurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: PurchaseOrderCreate) =>
      apiClient('/purchase-orders/', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['purchase-orders'] }),
  });
}

export function useSubmitPurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiClient(`/purchase-orders/${id}/submit/`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['purchase-orders'] }),
  });
}

export function useReceivePurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, items }: { id: number; items: Array<{ id: number; quantity_received: string }> }) =>
      apiClient(`/purchase-orders/${id}/receive/`, { method: 'POST', body: JSON.stringify({ items }) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchase-orders'] });
      queryClient.invalidateQueries({ queryKey: ['outlet-stock'] });
      queryClient.invalidateQueries({ queryKey: ['products'] });
    },
  });
}

export function useCancelPurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiClient(`/purchase-orders/${id}/cancel/`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['purchase-orders'] }),
  });
}

// ─── Stock Transfers ──────────────────────────────────────────────────────────

export function useStockTransfers(params: { status?: string; page?: number } = {}) {
  return useQuery<PaginatedResponse<StockTransfer>>({
    queryKey: ['stock-transfers', params],
    queryFn: () => {
      const query = new URLSearchParams();
      if (params.status) query.append('status', params.status);
      if (params.page) query.append('page', String(params.page));
      return apiClient(`/stock-transfers/?${query.toString()}`);
    },
  });
}

export function useCreateStockTransfer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: StockTransferCreate) =>
      apiClient('/stock-transfers/', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['stock-transfers'] }),
  });
}

export function useDispatchTransfer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiClient(`/stock-transfers/${id}/dispatch/`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['stock-transfers'] }),
  });
}

export function useReceiveTransfer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiClient(`/stock-transfers/${id}/receive/`, { method: 'POST' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stock-transfers'] });
      queryClient.invalidateQueries({ queryKey: ['outlet-stock'] });
    },
  });
}

export function useCancelTransfer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiClient(`/stock-transfers/${id}/cancel/`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['stock-transfers'] }),
  });
}

// ─── Stock Audit Log ──────────────────────────────────────────────────────────

export function useStockAuditLog(params: {
  product?: number;
  outlet?: number;
  movement_type?: string;
  page?: number;
} = {}) {
  return useQuery<PaginatedResponse<StockAuditLog>>({
    queryKey: ['stock-audit-log', params],
    queryFn: () => {
      const query = new URLSearchParams();
      if (params.product) query.append('product', String(params.product));
      if (params.outlet) query.append('outlet', String(params.outlet));
      if (params.movement_type) query.append('movement_type', params.movement_type);
      if (params.page) query.append('page', String(params.page));
      return apiClient(`/stock-audit-log/?${query.toString()}`);
    },
  });
}
```

**Verification checklist**:
- [ ] `grep -n 'export function' frontend/src/lib/hooks/useInventory.ts` → 14 exports
- [ ] No invented endpoints (all match Allowed API Reference)
- [ ] `useReceivePurchaseOrder` invalidates `products` + `outlet-stock` keys

---

## Phase 3: Reports Hooks

**File**: `frontend/src/lib/hooks/useReports.ts` (create new file)
**Copy pattern from**: `frontend/src/lib/hooks/useProducts.ts`

```typescript
'use client';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../api';
import type {
  DashboardData,
  SalesSummary,
  SalesByOutlet,
  SalesByProduct,
  SalesByPaymentMethod,
  HourlySales,
  StockLevel,
  StockAuditLog,
  ShiftSummaryReport,
} from '../types';

interface ReportDateParams {
  date_from?: string;
  date_to?: string;
  outlet?: number;
}

function buildReportQuery(params: Record<string, string | number | boolean | undefined>) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') query.append(k, String(v));
  });
  return query.toString();
}

export function useDashboard() {
  return useQuery<DashboardData>({
    queryKey: ['reports', 'dashboard'],
    queryFn: () => apiClient('/reports/dashboard/'),
    staleTime: 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  });
}

export function useSalesSummary(params: ReportDateParams = {}) {
  return useQuery<SalesSummary>({
    queryKey: ['reports', 'sales-summary', params],
    queryFn: () => apiClient(`/reports/sales-summary/?${buildReportQuery(params)}`),
  });
}

export function useSalesByOutlet(params: ReportDateParams = {}) {
  return useQuery<SalesByOutlet[]>({
    queryKey: ['reports', 'sales-by-outlet', params],
    queryFn: () => apiClient(`/reports/sales-by-outlet/?${buildReportQuery(params)}`),
  });
}

export function useSalesByProduct(params: ReportDateParams & { category?: number } = {}) {
  return useQuery<SalesByProduct[]>({
    queryKey: ['reports', 'sales-by-product', params],
    queryFn: () => apiClient(`/reports/sales-by-product/?${buildReportQuery(params)}`),
  });
}

export function useSalesByPaymentMethod(params: ReportDateParams = {}) {
  return useQuery<SalesByPaymentMethod[]>({
    queryKey: ['reports', 'sales-by-payment-method', params],
    queryFn: () => apiClient(`/reports/sales-by-payment-method/?${buildReportQuery(params)}`),
  });
}

export function useHourlySales(params: { date?: string; outlet?: number } = {}) {
  return useQuery<HourlySales[]>({
    queryKey: ['reports', 'hourly-sales', params],
    queryFn: () => apiClient(`/reports/hourly-sales/?${buildReportQuery(params)}`),
  });
}

export function useStockLevels(params: { outlet?: number; low_stock?: boolean } = {}) {
  return useQuery<StockLevel[]>({
    queryKey: ['reports', 'stock-levels', params],
    queryFn: () => apiClient(`/reports/stock-levels/?${buildReportQuery(params)}`),
  });
}

export function useStockMovement(params: ReportDateParams & { product?: number; movement_type?: string } = {}) {
  return useQuery<StockAuditLog[]>({
    queryKey: ['reports', 'stock-movement', params],
    queryFn: () => apiClient(`/reports/stock-movement/?${buildReportQuery(params)}`),
  });
}

export function useShiftSummary(params: ReportDateParams & { user_id?: number } = {}) {
  return useQuery<ShiftSummaryReport[]>({
    queryKey: ['reports', 'shift-summary', params],
    queryFn: () => apiClient(`/reports/shift-summary/?${buildReportQuery(params)}`),
  });
}
```

**Verification checklist**:
- [ ] `grep -n 'export function' frontend/src/lib/hooks/useReports.ts` → 9 exports
- [ ] `useDashboard` has `staleTime` and `refetchInterval`
- [ ] All endpoints match `/reports/` prefix exactly

---

## Phase 4: Users Hook

**File**: `frontend/src/lib/hooks/useUsers.ts` (create new file)
**Copy pattern from**: `frontend/src/lib/hooks/useProducts.ts`

```typescript
'use client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api';
import type { PaginatedResponse, User } from '../types';

export function useUsers(params: { search?: string; role?: string; is_active?: boolean; page?: number } = {}) {
  return useQuery<PaginatedResponse<User>>({
    queryKey: ['users', params],
    queryFn: () => {
      const query = new URLSearchParams();
      if (params.search) query.append('search', params.search);
      if (params.role) query.append('role', params.role);
      if (params.is_active !== undefined) query.append('is_active', String(params.is_active));
      if (params.page) query.append('page', String(params.page));
      return apiClient(`/users/?${query.toString()}`);
    },
  });
}

export function useUser(id: number) {
  return useQuery<User>({
    queryKey: ['users', id],
    queryFn: () => apiClient(`/users/${id}/`),
    enabled: !!id,
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<User> & { password: string }) =>
      apiClient('/users/', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: Partial<User> & { id: number }) =>
      apiClient(`/users/${id}/`, { method: 'PATCH', body: JSON.stringify(data) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  });
}

export function useDeactivateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiClient(`/users/${id}/deactivate/`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  });
}

export function useActivateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiClient(`/users/${id}/activate/`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  });
}
```

**Verification checklist**:
- [ ] `grep -n 'export function' frontend/src/lib/hooks/useUsers.ts` → 6 exports
- [ ] `useDeactivateUser` / `useActivateUser` use `/deactivate/` and `/activate/` paths

---

## Phase 5: Inventory Page Rebuild

**File**: `frontend/src/app/dashboard/inventory/page.tsx`

**Scope**: Full rebuild — replace all hardcoded arrays with real API data
**Reference for tab structure**: Keep existing 5-tab layout but wire each tab to real data
**Reference for loading/error patterns**: Check `frontend/src/app/dashboard/sales/page.tsx` for loading skeleton + error display pattern

### Tab 1: Stock Overview
- Import: `useProducts`, `useLowOutletStock`
- KPI cards: product count from `useProducts().data?.count`, low stock from `useLowOutletStock().data?.count`
- Products table: `useProducts({ page })` with pagination state
- Per-row: name, SKU, category_name, stock_quantity, reorder_level, is_low_stock badge
- Filter: category dropdown, search input with debounce
- Loading: skeleton rows during `isLoading`
- Error: error alert when `isError`

### Tab 2: Purchase Orders
- Import: `usePurchaseOrders`, `useCreatePurchaseOrder`, `useSubmitPurchaseOrder`, `useReceivePurchaseOrder`, `useCancelPurchaseOrder`
- List: `usePurchaseOrders({ status, page })` with status filter dropdown
- Status badges: draft (gray), submitted (blue), partial (yellow), received (green), cancelled (red)
- Actions per row: Submit (draft only), Receive (submitted/partial only), Cancel (draft/submitted only)
- Create modal: supplier select (from `useSuppliers()`), outlet select, date picker, line items (product + qty + cost)
- Receive modal: for each item show qty_ordered vs qty_received input
- Cancel: confirm dialog before calling mutation

### Tab 3: Stock Transfers
- Import: `useStockTransfers`, `useCreateStockTransfer`, `useDispatchTransfer`, `useReceiveTransfer`, `useCancelTransfer`
- List: `useStockTransfers({ status, page })`
- Status badges: pending (gray), in_transit (blue), completed (green), cancelled (red)
- Actions: Dispatch (pending), Receive (in_transit), Cancel (pending only)
- Create modal: from_outlet + to_outlet selects, line items

### Tab 4: Suppliers
- Import: `useSuppliers`, `useCreateSupplier`, `useUpdateSupplier`, `useDeleteSupplier`
- Table: name, contact_person, email, phone, is_active badge
- Search input filters list
- Edit modal / Create modal with form fields
- Delete: confirm dialog before calling mutation

### Tab 5: Audit Log
- Import: `useStockAuditLog`
- Readonly table: product_name, outlet_name, movement_type_display, quantity_change, quantity_before, quantity_after, created_at
- Filters: movement_type dropdown, outlet select
- Pagination

**Verification checklist**:
- [ ] `grep 'const.*=.*\[\]' frontend/src/app/dashboard/inventory/page.tsx` → returns empty (no hardcoded arrays)
- [ ] `grep 'isLoading\|isError' frontend/src/app/dashboard/inventory/page.tsx` → found (loading/error handled)
- [ ] `grep 'usePurchaseOrders\|useSuppliers\|useStockTransfers' frontend/src/app/dashboard/inventory/page.tsx` → found

---

## Phase 6: Reports Page Rebuild

**File**: `frontend/src/app/dashboard/reports/page.tsx`

**Scope**: Full rebuild — add date range picker and wire all 9 report endpoints

### Layout
```
[Date Range: From ______ To ______] [Outlet: All ▼] [Refresh ↻]

Tab: Sales | Inventory | Shifts

[Tab: Sales]
  ┌─ Summary KPIs (useSalesSummary) ──────────────────────────────────┐
  │  Total Sales: 142  |  Revenue: UGX 14.2M  |  Avg: UGX 100K      │
  └──────────────────────────────────────────────────────────────────┘

  [By Outlet table (useSalesByOutlet)]
  [By Product top-20 table (useSalesByProduct)]
  [Payment Method breakdown table (useSalesByPaymentMethod)]
  [Hourly trends bar chart (useHourlySales)]

[Tab: Inventory]
  [Stock Levels table (useStockLevels) with low_stock filter toggle]
  [Stock Movement table (useStockMovement) with movement_type filter]

[Tab: Shifts]
  [Shift Summary table (useShiftSummary)]
```

### State management
```typescript
const [dateFrom, setDateFrom] = useState<string>('');
const [dateTo, setDateTo] = useState<string>('');
const [outlet, setOutlet] = useState<number | undefined>();
const [activeTab, setActiveTab] = useState<'sales' | 'inventory' | 'shifts'>('sales');

const reportParams = { date_from: dateFrom || undefined, date_to: dateTo || undefined, outlet };
```

### Imports needed
```typescript
import {
  useSalesSummary, useSalesByOutlet, useSalesByProduct,
  useSalesByPaymentMethod, useHourlySales,
  useStockLevels, useStockMovement, useShiftSummary
} from '@/lib/hooks/useReports';
import { useOutlets } from '@/lib/hooks/useOutlets';
```

**Verification checklist**:
- [ ] `grep 'const.*=.*\[\]' frontend/src/app/dashboard/reports/page.tsx` → empty (no hardcoded arrays)
- [ ] Date range inputs affect all queries
- [ ] Loading states present on each data section

---

## Phase 7: Main Dashboard Wiring

**File**: `frontend/src/app/dashboard/page.tsx`

**Scope**: Minimal — replace hardcoded KPI numbers with `useDashboard()` data

### Changes
```typescript
// Add import
import { useDashboard } from '@/lib/hooks/useReports';
import { useSales } from '@/lib/hooks/useSales';

// In component
const { data: dashData, isLoading: dashLoading } = useDashboard();
const { data: recentSales } = useSales({ page: 1 });

// Replace hardcoded values:
// "UGX 14.2M" → formatCurrency(dashData?.today_revenue)
// "142 sales" → dashData?.today_sales_count
// Low stock count → dashData?.low_stock_count
// Recent transactions → recentSales?.results.slice(0, 5)
```

**Verification checklist**:
- [ ] `grep 'useDashboard' frontend/src/app/dashboard/page.tsx` → found
- [ ] No hardcoded `14.2M` or similar revenue numbers

---

## Phase 8: Employees Page Wiring

**File**: `frontend/src/app/dashboard/employees/page.tsx`

**Scope**: Replace mock employee array with real `useUsers()` data

### Changes
```typescript
// Add import
import { useUsers, useCreateUser, useUpdateUser, useDeactivateUser, useActivateUser } from '@/lib/hooks/useUsers';

// In component
const [search, setSearch] = useState('');
const [roleFilter, setRoleFilter] = useState('');
const [page, setPage] = useState(1);
const { data, isLoading, isError } = useUsers({ search, role: roleFilter, page });

// Replace mock employees array with data?.results
// Replace static "52 employees" KPI with data?.count
// Add loading skeleton rows
// Create employee modal calls useCreateUser()
// Activate/deactivate buttons call useActivateUser/useDeactivateUser
```

**Note**: Attendance and Leave tabs can remain as placeholders — those backend modules don't exist yet. Add a "Coming soon" placeholder instead of hardcoded mock data.

**Verification checklist**:
- [ ] `grep 'useUsers' frontend/src/app/dashboard/employees/page.tsx` → found
- [ ] No hardcoded employee array (52 mock employees removed)

---

## Final Verification

Run after all phases are complete:

```bash
# 1. Start backend
docker-compose up -d

# 2. Check TypeScript compiles
cd frontend && npx tsc --noEmit

# 3. Verify hooks exist
grep -n 'export function' frontend/src/lib/hooks/useInventory.ts  # expect 14
grep -n 'export function' frontend/src/lib/hooks/useReports.ts    # expect 9
grep -n 'export function' frontend/src/lib/hooks/useUsers.ts      # expect 6

# 4. Check no hardcoded arrays remain in target pages
grep -n 'const.*=.*\[{' frontend/src/app/dashboard/inventory/page.tsx
grep -n 'const.*=.*\[{' frontend/src/app/dashboard/reports/page.tsx

# 5. Browser test
# Navigate to /dashboard — KPIs should show real data
# Navigate to /dashboard/inventory — tables should load from API
# Navigate to /dashboard/reports — date filter should work
# Navigate to /dashboard/employees — user list should load
```

---

## Out of Scope (Phase 5+)
- **Accounting page**: Backend not built for chart-of-accounts, journal entries, or tax management
- **Fuel-specific features**: Tank levels, pump management (not in current backend)
- **Leave management / Attendance**: Backend not built
- **WebSocket / real-time**: Not in current architecture
- **PDF/Excel report export**: Not in current backend
- **Multi-tenancy admin UI**: Infrastructure-level concern
