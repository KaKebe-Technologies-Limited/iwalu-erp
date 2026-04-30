'use client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api';
import type {
  PaginatedResponse,
  Account,
  FiscalPeriod,
  JournalEntry,
  JournalEntryCreate,
  TrialBalanceLine,
  ProfitLoss,
  BalanceSheet,
} from '../types';

// ─── Accounts ────────────────────────────────────────────────────────────────

export function useAccounts(params: {
  search?: string;
  account_type?: string;
  is_active?: boolean;
  root?: boolean;
  page?: number;
} = {}) {
  return useQuery<PaginatedResponse<Account>>({
    queryKey: ['accounts', params],
    queryFn: () => {
      const query = new URLSearchParams();
      if (params.search) query.append('search', params.search);
      if (params.account_type) query.append('account_type', params.account_type);
      if (params.is_active !== undefined) query.append('is_active', String(params.is_active));
      if (params.root) query.append('root', 'true');
      if (params.page) query.append('page', String(params.page));
      return apiClient(`/accounts/?${query.toString()}`);
    },
  });
}

export function useCreateAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Account>) =>
      apiClient('/accounts/', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['accounts'] }),
  });
}

// ─── Fiscal Periods ───────────────────────────────────────────────────────────

export function useFiscalPeriods() {
  return useQuery<PaginatedResponse<FiscalPeriod>>({
    queryKey: ['fiscal-periods'],
    queryFn: () => apiClient('/fiscal-periods/'),
  });
}

// ─── Journal Entries ──────────────────────────────────────────────────────────

export function useJournalEntries(params: {
  status?: string;
  source?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
} = {}) {
  return useQuery<PaginatedResponse<JournalEntry>>({
    queryKey: ['journal-entries', params],
    queryFn: () => {
      const query = new URLSearchParams();
      if (params.status) query.append('status', params.status);
      if (params.source) query.append('source', params.source);
      if (params.date_from) query.append('date_from', params.date_from);
      if (params.date_to) query.append('date_to', params.date_to);
      if (params.page) query.append('page', String(params.page));
      return apiClient(`/journal-entries/?${query.toString()}`);
    },
  });
}

export function useCreateJournalEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: JournalEntryCreate) =>
      apiClient('/journal-entries/', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['journal-entries'] }),
  });
}

export function usePostJournalEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiClient(`/journal-entries/${id}/post/`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['journal-entries'] }),
  });
}

export function useVoidJournalEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiClient(`/journal-entries/${id}/void/`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['journal-entries'] }),
  });
}

// ─── Financial Reports ────────────────────────────────────────────────────────

export function useTrialBalance(params: { as_of_date?: string; outlet?: number } = {}) {
  return useQuery<TrialBalanceLine[]>({
    queryKey: ['trial-balance', params],
    queryFn: () => {
      const query = new URLSearchParams();
      if (params.as_of_date) query.append('as_of_date', params.as_of_date);
      if (params.outlet) query.append('outlet', String(params.outlet));
      return apiClient(`/finance/trial-balance/?${query.toString()}`);
    },
  });
}

export function useProfitLoss(params: { date_from: string; date_to: string; outlet?: number }) {
  return useQuery<ProfitLoss>({
    queryKey: ['profit-loss', params],
    queryFn: () => {
      const query = new URLSearchParams();
      query.append('date_from', params.date_from);
      query.append('date_to', params.date_to);
      if (params.outlet) query.append('outlet', String(params.outlet));
      return apiClient(`/finance/profit-loss/?${query.toString()}`);
    },
    enabled: !!params.date_from && !!params.date_to,
  });
}

export function useBalanceSheet(params: { as_of_date?: string; outlet?: number } = {}) {
  return useQuery<BalanceSheet>({
    queryKey: ['balance-sheet', params],
    queryFn: () => {
      const query = new URLSearchParams();
      if (params.as_of_date) query.append('as_of_date', params.as_of_date);
      if (params.outlet) query.append('outlet', String(params.outlet));
      return apiClient(`/finance/balance-sheet/?${query.toString()}`);
    },
  });
}
