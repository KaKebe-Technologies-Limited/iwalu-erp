import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';
import type { PaginatedResponse, OutletStock } from '@/lib/types';

export function useOutletStock(params: { outlet?: string; product?: string; page?: number } = {}) {
  const query = new URLSearchParams();
  if (params.outlet) query.set('outlet', params.outlet);
  if (params.product) query.set('product', params.product);
  if (params.page) query.set('page', String(params.page));

  return useQuery<PaginatedResponse<OutletStock>>({
    queryKey: ['outlet-stock', params],
    queryFn: () => apiClient(`/outlet-stock/?${query.toString()}`),
  });
}

export function useLowOutletStock(outlet?: string) {
  const query = new URLSearchParams();
  if (outlet) query.set('outlet', outlet);

  return useQuery<PaginatedResponse<OutletStock>>({
    queryKey: ['outlet-stock', 'low', outlet],
    queryFn: () => apiClient(`/outlet-stock/low/?${query.toString()}`),
  });
}
