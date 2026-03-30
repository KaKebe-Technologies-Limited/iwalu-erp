import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';
import type { PaginatedResponse, PurchaseOrder } from '@/lib/types';

export function usePurchaseOrders(params: { search?: string; supplier?: string; outlet?: string; status?: string; page?: number } = {}) {
  const query = new URLSearchParams();
  if (params.search) query.set('search', params.search);
  if (params.supplier) query.set('supplier', params.supplier);
  if (params.outlet) query.set('outlet', params.outlet);
  if (params.status) query.set('status', params.status);
  if (params.page) query.set('page', String(params.page));

  return useQuery<PaginatedResponse<PurchaseOrder>>({
    queryKey: ['purchase-orders', params],
    queryFn: () => apiClient(`/purchase-orders/?${query.toString()}`),
  });
}

export function usePurchaseOrder(id: number) {
  return useQuery<PurchaseOrder>({
    queryKey: ['purchase-orders', id],
    queryFn: () => apiClient(`/purchase-orders/${id}/`),
    enabled: !!id,
  });
}

interface CreatePOData {
  supplier_id: number;
  outlet_id: number;
  expected_date?: string;
  notes?: string;
  items: Array<{ product_id: number; quantity_ordered: string; unit_cost: string }>;
}

export function useCreatePurchaseOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreatePOData) =>
      apiClient('/purchase-orders/', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['purchase-orders'] }),
  });
}

export function useSubmitPurchaseOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiClient(`/purchase-orders/${id}/submit/`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['purchase-orders'] }),
  });
}

export function useReceivePurchaseOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, items }: { id: number; items: Array<{ po_item_id: number; quantity_received: string }> }) =>
      apiClient(`/purchase-orders/${id}/receive/`, { method: 'POST', body: JSON.stringify({ items }) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['purchase-orders'] });
      qc.invalidateQueries({ queryKey: ['outlet-stock'] });
      qc.invalidateQueries({ queryKey: ['stock-audit-log'] });
      qc.invalidateQueries({ queryKey: ['products'] });
    },
  });
}

export function useCancelPurchaseOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiClient(`/purchase-orders/${id}/cancel/`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['purchase-orders'] }),
  });
}
