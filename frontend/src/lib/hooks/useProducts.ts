import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';
import type { PaginatedResponse, Product } from '@/lib/types';

export function useProducts(params: { search?: string; category?: string; is_active?: string; page?: number } = {}) {
  const query = new URLSearchParams();
  if (params.search) query.set('search', params.search);
  if (params.category) query.set('category', params.category);
  if (params.is_active) query.set('is_active', params.is_active);
  if (params.page) query.set('page', String(params.page));

  return useQuery<PaginatedResponse<Product>>({
    queryKey: ['products', params],
    queryFn: () => apiClient(`/products/?${query.toString()}`),
  });
}

export function useProduct(id: number) {
  return useQuery<Product>({
    queryKey: ['products', id],
    queryFn: () => apiClient(`/products/${id}/`),
    enabled: !!id,
  });
}

export function useLowStockProducts() {
  return useQuery<PaginatedResponse<Product>>({
    queryKey: ['products', 'low_stock'],
    queryFn: () => apiClient('/products/low_stock/'),
  });
}

export function useCreateProduct() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Product>) =>
      apiClient('/products/', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['products'] }),
  });
}

export function useUpdateProduct() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: Partial<Product> & { id: number }) =>
      apiClient(`/products/${id}/`, { method: 'PATCH', body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['products'] }),
  });
}

export function useAdjustStock() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, quantity, reason }: { id: number; quantity: string; reason: string }) =>
      apiClient(`/products/${id}/adjust_stock/`, { method: 'POST', body: JSON.stringify({ quantity, reason }) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['products'] }),
  });
}
