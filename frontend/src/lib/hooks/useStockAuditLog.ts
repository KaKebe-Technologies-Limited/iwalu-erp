import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';
import type { PaginatedResponse, StockAuditLog } from '@/lib/types';

export function useStockAuditLog(params: { product?: string; outlet?: string; movement_type?: string; page?: number } = {}) {
  const query = new URLSearchParams();
  if (params.product) query.set('product', params.product);
  if (params.outlet) query.set('outlet', params.outlet);
  if (params.movement_type) query.set('movement_type', params.movement_type);
  if (params.page) query.set('page', String(params.page));

  return useQuery<PaginatedResponse<StockAuditLog>>({
    queryKey: ['stock-audit-log', params],
    queryFn: () => apiClient(`/stock-audit-log/?${query.toString()}`),
  });
}
