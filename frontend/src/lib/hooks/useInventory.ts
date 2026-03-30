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
