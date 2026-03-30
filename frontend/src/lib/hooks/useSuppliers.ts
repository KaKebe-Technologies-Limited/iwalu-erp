import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';
import type { PaginatedResponse, Supplier } from '@/lib/types';

export function useSuppliers(params: { search?: string; is_active?: string; page?: number } = {}) {
  const query = new URLSearchParams();
  if (params.search) query.set('search', params.search);
  if (params.is_active) query.set('is_active', params.is_active);
  if (params.page) query.set('page', String(params.page));

  return useQuery<PaginatedResponse<Supplier>>({
    queryKey: ['suppliers', params],
    queryFn: () => apiClient(`/suppliers/?${query.toString()}`),
  });
}

export function useSupplier(id: number) {
  return useQuery<Supplier>({
    queryKey: ['suppliers', id],
    queryFn: () => apiClient(`/suppliers/${id}/`),
    enabled: !!id,
  });
}

export function useCreateSupplier() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Supplier>) =>
      apiClient('/suppliers/', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['suppliers'] }),
  });
}

export function useUpdateSupplier() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: Partial<Supplier> & { id: number }) =>
      apiClient(`/suppliers/${id}/`, { method: 'PATCH', body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['suppliers'] }),
  });
}

export function useDeleteSupplier() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiClient(`/suppliers/${id}/`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['suppliers'] }),
  });
}
