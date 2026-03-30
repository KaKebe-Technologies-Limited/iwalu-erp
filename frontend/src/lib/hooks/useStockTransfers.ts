import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';
import type { PaginatedResponse, StockTransfer } from '@/lib/types';

export function useStockTransfers(params: { search?: string; from_outlet?: string; to_outlet?: string; status?: string; page?: number } = {}) {
  const query = new URLSearchParams();
  if (params.search) query.set('search', params.search);
  if (params.from_outlet) query.set('from_outlet', params.from_outlet);
  if (params.to_outlet) query.set('to_outlet', params.to_outlet);
  if (params.status) query.set('status', params.status);
  if (params.page) query.set('page', String(params.page));

  return useQuery<PaginatedResponse<StockTransfer>>({
    queryKey: ['stock-transfers', params],
    queryFn: () => apiClient(`/stock-transfers/?${query.toString()}`),
  });
}

export function useStockTransfer(id: number) {
  return useQuery<StockTransfer>({
    queryKey: ['stock-transfers', id],
    queryFn: () => apiClient(`/stock-transfers/${id}/`),
    enabled: !!id,
  });
}

interface CreateTransferData {
  from_outlet_id: number;
  to_outlet_id: number;
  notes?: string;
  items: Array<{ product_id: number; quantity: string }>;
}

export function useCreateStockTransfer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateTransferData) =>
      apiClient('/stock-transfers/', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['stock-transfers'] }),
  });
}

export function useDispatchTransfer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiClient(`/stock-transfers/${id}/dispatch/`, { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['stock-transfers'] });
      qc.invalidateQueries({ queryKey: ['outlet-stock'] });
      qc.invalidateQueries({ queryKey: ['stock-audit-log'] });
    },
  });
}

export function useReceiveTransfer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, items }: { id: number; items: Array<{ transfer_item_id: number; quantity_received: string }> }) =>
      apiClient(`/stock-transfers/${id}/receive/`, { method: 'POST', body: JSON.stringify({ items }) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['stock-transfers'] });
      qc.invalidateQueries({ queryKey: ['outlet-stock'] });
      qc.invalidateQueries({ queryKey: ['stock-audit-log'] });
    },
  });
}

export function useCancelTransfer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiClient(`/stock-transfers/${id}/cancel/`, { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['stock-transfers'] }),
  });
}
