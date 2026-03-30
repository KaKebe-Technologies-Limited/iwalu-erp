'use client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api';
import type { PaginatedResponse, User } from '../types';

export function useUsers(params: { search?: string; role?: string; is_active?: boolean; page?: number } = {}) {
  return useQuery<PaginatedResponse<User>>({
    queryKey: ['users', params],
    queryFn: () => {
      const query = new URLSearchParams();
      if (params.search) query.append('search', params.search);
      if (params.role) query.append('role', params.role);
      if (params.is_active !== undefined) query.append('is_active', String(params.is_active));
      if (params.page) query.append('page', String(params.page));
      return apiClient(`/users/?${query.toString()}`);
    },
  });
}

export function useUser(id: number) {
  return useQuery<User>({
    queryKey: ['users', id],
    queryFn: () => apiClient(`/users/${id}/`),
    enabled: !!id,
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<User> & { password: string }) =>
      apiClient('/users/', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: Partial<User> & { id: number }) =>
      apiClient(`/users/${id}/`, { method: 'PATCH', body: JSON.stringify(data) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  });
}

export function useDeactivateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiClient(`/users/${id}/deactivate/`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  });
}

export function useActivateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiClient(`/users/${id}/activate/`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['users'] }),
  });
}
