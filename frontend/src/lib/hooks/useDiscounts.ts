import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';
import type { PaginatedResponse, Discount } from '@/lib/types';

export function useDiscounts(params: { discount_type?: string; is_active?: string; page?: number } = {}) {
  const query = new URLSearchParams();
  if (params.discount_type) query.set('discount_type', params.discount_type);
  if (params.is_active) query.set('is_active', params.is_active);
  if (params.page) query.set('page', String(params.page));

  return useQuery<PaginatedResponse<Discount>>({
    queryKey: ['discounts', params],
    queryFn: () => apiClient(`/discounts/?${query.toString()}`),
  });
}

export function useCreateDiscount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Discount>) =>
      apiClient('/discounts/', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['discounts'] }),
  });
}

export function useUpdateDiscount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: Partial<Discount> & { id: number }) =>
      apiClient(`/discounts/${id}/`, { method: 'PATCH', body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['discounts'] }),
  });
}

export function useDeleteDiscount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiClient(`/discounts/${id}/`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['discounts'] }),
  });
}
