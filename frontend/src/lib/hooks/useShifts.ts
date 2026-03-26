import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';
import type { PaginatedResponse, Shift } from '@/lib/types';

export function useShifts(params: { outlet?: string; status?: string; page?: number } = {}) {
  const query = new URLSearchParams();
  if (params.outlet) query.set('outlet', params.outlet);
  if (params.status) query.set('status', params.status);
  if (params.page) query.set('page', String(params.page));

  return useQuery<PaginatedResponse<Shift>>({
    queryKey: ['shifts', params],
    queryFn: () => apiClient(`/shifts/?${query.toString()}`),
  });
}

export function useMyCurrentShift() {
  return useQuery<Shift | null>({
    queryKey: ['shifts', 'my_current'],
    queryFn: () => apiClient('/shifts/my_current/').catch(() => null),
  });
}

export function useOpenShift() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { outlet: number; opening_cash: string }) =>
      apiClient('/shifts/open/', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['shifts'] });
    },
  });
}

export function useCloseShift() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, closing_cash, notes }: { id: number; closing_cash: string; notes?: string }) =>
      apiClient(`/shifts/${id}/close/`, { method: 'POST', body: JSON.stringify({ closing_cash, notes }) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['shifts'] });
    },
  });
}
