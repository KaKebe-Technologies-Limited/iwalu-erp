import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';
import type { PaginatedResponse, Sale, CheckoutRequest } from '@/lib/types';

export function useSales(params: { search?: string; outlet?: string; status?: string; shift?: string; page?: number } = {}) {
  const query = new URLSearchParams();
  if (params.search) query.set('search', params.search);
  if (params.outlet) query.set('outlet', params.outlet);
  if (params.status) query.set('status', params.status);
  if (params.shift) query.set('shift', params.shift);
  if (params.page) query.set('page', String(params.page));

  return useQuery<PaginatedResponse<Sale>>({
    queryKey: ['sales', params],
    queryFn: () => apiClient(`/sales/?${query.toString()}`),
  });
}

export function useSale(id: number) {
  return useQuery<Sale>({
    queryKey: ['sales', id],
    queryFn: () => apiClient(`/sales/${id}/`),
    enabled: !!id,
  });
}

export function useSaleReceipt(id: number) {
  return useQuery({
    queryKey: ['sales', id, 'receipt'],
    queryFn: () => apiClient(`/sales/${id}/receipt/`),
    enabled: !!id,
  });
}

export function useCheckout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CheckoutRequest) =>
      apiClient('/checkout/', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sales'] });
      qc.invalidateQueries({ queryKey: ['shifts'] });
      qc.invalidateQueries({ queryKey: ['products'] });
    },
  });
}

export function useVoidSale() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiClient(`/sales/${id}/void/`, { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sales'] });
      qc.invalidateQueries({ queryKey: ['products'] });
    },
  });
}
