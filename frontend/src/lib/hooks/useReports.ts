import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';
import type {
  DashboardData,
  SalesSummary,
  SalesByOutlet,
  SalesByProduct,
  SalesByPaymentMethod,
  HourlySales,
  StockLevel,
  StockMovementSummary,
  ShiftSummaryEntry,
} from '@/lib/types';

interface DateRangeParams {
  date_from?: string;
  date_to?: string;
  outlet?: string;
}

function buildQuery(params: DateRangeParams & Record<string, string | undefined>) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) query.set(key, value);
  }
  return query.toString();
}

export function useDashboard(outlet?: string) {
  const query = new URLSearchParams();
  if (outlet) query.set('outlet', outlet);

  return useQuery<DashboardData>({
    queryKey: ['reports', 'dashboard', outlet],
    queryFn: () => apiClient(`/reports/dashboard/?${query.toString()}`),
  });
}

export function useSalesSummary(params: DateRangeParams = {}) {
  return useQuery<SalesSummary>({
    queryKey: ['reports', 'sales-summary', params],
    queryFn: () => apiClient(`/reports/sales-summary/?${buildQuery(params)}`),
  });
}

export function useSalesByOutlet(params: Omit<DateRangeParams, 'outlet'> = {}) {
  return useQuery<SalesByOutlet[]>({
    queryKey: ['reports', 'sales-by-outlet', params],
    queryFn: () => apiClient(`/reports/sales-by-outlet/?${buildQuery(params)}`),
  });
}

export function useSalesByProduct(params: DateRangeParams & { category?: string } = {}) {
  return useQuery<SalesByProduct[]>({
    queryKey: ['reports', 'sales-by-product', params],
    queryFn: () => apiClient(`/reports/sales-by-product/?${buildQuery(params)}`),
  });
}

export function useSalesByPaymentMethod(params: DateRangeParams = {}) {
  return useQuery<SalesByPaymentMethod[]>({
    queryKey: ['reports', 'sales-by-payment-method', params],
    queryFn: () => apiClient(`/reports/sales-by-payment-method/?${buildQuery(params)}`),
  });
}

export function useHourlySales(params: DateRangeParams = {}) {
  return useQuery<HourlySales[]>({
    queryKey: ['reports', 'hourly-sales', params],
    queryFn: () => apiClient(`/reports/hourly-sales/?${buildQuery(params)}`),
  });
}

export function useStockLevels(params: { outlet?: string; category?: string } = {}) {
  return useQuery<StockLevel[]>({
    queryKey: ['reports', 'stock-levels', params],
    queryFn: () => apiClient(`/reports/stock-levels/?${buildQuery(params)}`),
  });
}

export function useStockMovement(params: DateRangeParams & { product?: string } = {}) {
  return useQuery<StockMovementSummary[]>({
    queryKey: ['reports', 'stock-movement', params],
    queryFn: () => apiClient(`/reports/stock-movement/?${buildQuery(params)}`),
  });
}

export function useShiftSummary(params: DateRangeParams & { user_id?: string } = {}) {
  return useQuery<ShiftSummaryEntry[]>({
    queryKey: ['reports', 'shift-summary', params],
    queryFn: () => apiClient(`/reports/shift-summary/?${buildQuery(params)}`),
  });
}
