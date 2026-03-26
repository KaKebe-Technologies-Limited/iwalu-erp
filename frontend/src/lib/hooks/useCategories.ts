import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';
import type { PaginatedResponse, Category } from '@/lib/types';

export function useCategories(params: { business_unit?: string; parent?: string; is_active?: string; page?: number } = {}) {
  const query = new URLSearchParams();
  if (params.business_unit) query.set('business_unit', params.business_unit);
  if (params.parent) query.set('parent', params.parent);
  if (params.is_active) query.set('is_active', params.is_active);
  if (params.page) query.set('page', String(params.page));

  return useQuery<PaginatedResponse<Category>>({
    queryKey: ['categories', params],
    queryFn: () => apiClient(`/categories/?${query.toString()}`),
  });
}

export function useCreateCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Category>) =>
      apiClient('/categories/', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['categories'] }),
  });
}

export function useUpdateCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: Partial<Category> & { id: number }) =>
      apiClient(`/categories/${id}/`, { method: 'PATCH', body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['categories'] }),
  });
}

export function useDeleteCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiClient(`/categories/${id}/`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['categories'] }),
  });
}
