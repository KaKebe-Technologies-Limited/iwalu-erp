import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';
import type { PaginatedResponse, Outlet } from '@/lib/types';

export function useOutlets(params: { search?: string; outlet_type?: string; is_active?: string; page?: number } = {}) {
  const query = new URLSearchParams();
  if (params.search) query.set('search', params.search);
  if (params.outlet_type) query.set('outlet_type', params.outlet_type);
  if (params.is_active) query.set('is_active', params.is_active);
  if (params.page) query.set('page', String(params.page));

  return useQuery<PaginatedResponse<Outlet>>({
    queryKey: ['outlets', params],
    queryFn: () => apiClient(`/outlets/?${query.toString()}`),
  });
}

export function useOutlet(id: number) {
  return useQuery<Outlet>({
    queryKey: ['outlets', id],
    queryFn: () => apiClient(`/outlets/${id}/`),
    enabled: !!id,
  });
}

export function useCreateOutlet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Outlet>) =>
      apiClient('/outlets/', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['outlets'] }),
  });
}

export function useUpdateOutlet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: Partial<Outlet> & { id: number }) =>
      apiClient(`/outlets/${id}/`, { method: 'PATCH', body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['outlets'] }),
  });
}

export function useDeleteOutlet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiClient(`/outlets/${id}/`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['outlets'] }),
  });
}
