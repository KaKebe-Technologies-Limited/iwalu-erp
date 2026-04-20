import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api";
import type {
  Pump, Tank, TankReading, PumpReading,
  FuelDelivery, FuelReconciliation,
  DailyPumpReport, VarianceReport,
} from "@/lib/types";

interface Paginated<T> {
  count: number;
  results: T[];
}

// ── Pumps ────────────────────────────────────────────────────────────────────

export function usePumps(params?: { outlet?: number; status?: string }) {
  const qs = new URLSearchParams();
  if (params?.outlet) qs.set("outlet", String(params.outlet));
  if (params?.status) qs.set("status", params.status);
  return useQuery({
    queryKey: ["fuel-pumps", params],
    queryFn: () => apiClient<Paginated<Pump>>(`/fuel/pumps/?${qs}`),
  });
}

export function useActivatePump() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiClient(`/fuel/pumps/${id}/activate/`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["fuel-pumps"] }),
  });
}

export function useDeactivatePump() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiClient(`/fuel/pumps/${id}/deactivate/`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["fuel-pumps"] }),
  });
}

export function useSetPumpMaintenance() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiClient(`/fuel/pumps/${id}/set-maintenance/`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["fuel-pumps"] }),
  });
}

// ── Tanks ────────────────────────────────────────────────────────────────────

export function useTanks(params?: { outlet?: number }) {
  const qs = new URLSearchParams();
  if (params?.outlet) qs.set("outlet", String(params.outlet));
  return useQuery({
    queryKey: ["fuel-tanks", params],
    queryFn: () => apiClient<Paginated<Tank>>(`/fuel/tanks/?${qs}`),
  });
}

export function useTankLevelsSummary(params?: { outlet?: number }) {
  const qs = new URLSearchParams();
  if (params?.outlet) qs.set("outlet", String(params.outlet));
  return useQuery({
    queryKey: ["fuel-tank-levels", params],
    queryFn: () => apiClient<Tank[]>(`/fuel/reports/tank-levels/?${qs}`),
  });
}

export function useRecordTankReading() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      tankId,
      data,
    }: {
      tankId: number;
      data: { reading_level: string; reading_type: string; reading_at?: string; notes?: string };
    }) =>
      apiClient<TankReading>(`/fuel/tanks/${tankId}/record-reading/`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["fuel-tank-levels"] });
      qc.invalidateQueries({ queryKey: ["fuel-tanks"] });
    },
  });
}

// ── Pump Readings ─────────────────────────────────────────────────────────────

export function usePumpReadings(params?: { pump?: number; shift?: number; page?: number }) {
  const qs = new URLSearchParams();
  if (params?.pump) qs.set("pump", String(params.pump));
  if (params?.shift) qs.set("shift", String(params.shift));
  if (params?.page) qs.set("page", String(params.page));
  return useQuery({
    queryKey: ["fuel-pump-readings", params],
    queryFn: () => apiClient<Paginated<PumpReading>>(`/fuel/pump-readings/?${qs}`),
  });
}

export function useClosePumpReading() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      closing_reading,
      notes,
    }: {
      id: number;
      closing_reading: string;
      notes?: string;
    }) =>
      apiClient(`/fuel/pump-readings/${id}/close/`, {
        method: "POST",
        body: JSON.stringify({ closing_reading, notes }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["fuel-pump-readings"] }),
  });
}

// ── Deliveries ────────────────────────────────────────────────────────────────

export function useFuelDeliveries(params?: { tank?: number; page?: number }) {
  const qs = new URLSearchParams();
  if (params?.tank) qs.set("tank", String(params.tank));
  if (params?.page) qs.set("page", String(params.page));
  return useQuery({
    queryKey: ["fuel-deliveries", params],
    queryFn: () => apiClient<Paginated<FuelDelivery>>(`/fuel/deliveries/?${qs}`),
  });
}

export function useCreateFuelDelivery() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      tank_id: number;
      supplier_id: number;
      delivery_date: string;
      volume_ordered?: string;
      volume_received: string;
      unit_cost: string;
      delivery_note_number?: string;
      notes?: string;
    }) =>
      apiClient<FuelDelivery>("/fuel/deliveries/", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["fuel-deliveries"] });
      qc.invalidateQueries({ queryKey: ["fuel-tank-levels"] });
    },
  });
}

// ── Reconciliations ────────────────────────────────────────────────────────────

export function useFuelReconciliations(params?: {
  outlet?: number;
  date_from?: string;
  date_to?: string;
  page?: number;
}) {
  const qs = new URLSearchParams();
  if (params?.outlet) qs.set("outlet", String(params.outlet));
  if (params?.date_from) qs.set("date_from", params.date_from);
  if (params?.date_to) qs.set("date_to", params.date_to);
  if (params?.page) qs.set("page", String(params.page));
  return useQuery({
    queryKey: ["fuel-reconciliations", params],
    queryFn: () => apiClient<Paginated<FuelReconciliation>>(`/fuel/reconciliations/?${qs}`),
  });
}

export function useCalculateReconciliation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      tank_id: number;
      date: string;
      closing_stock?: string;
      notes?: string;
    }) =>
      apiClient<FuelReconciliation>("/fuel/reconciliations/calculate/", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["fuel-reconciliations"] }),
  });
}

export function useConfirmReconciliation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiClient<FuelReconciliation>(`/fuel/reconciliations/${id}/confirm/`, {
        method: "POST",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["fuel-reconciliations"] });
      qc.invalidateQueries({ queryKey: ["fuel-tank-levels"] });
    },
  });
}

export function useVarianceAlerts(params?: {
  outlet?: number;
  date_from?: string;
  date_to?: string;
}) {
  const qs = new URLSearchParams();
  if (params?.outlet) qs.set("outlet", String(params.outlet));
  if (params?.date_from) qs.set("date_from", params.date_from);
  if (params?.date_to) qs.set("date_to", params.date_to);
  return useQuery({
    queryKey: ["fuel-variance-alerts", params],
    queryFn: () =>
      apiClient<Paginated<FuelReconciliation>>(
        `/fuel/reconciliations/variance-alerts/?${qs}`,
      ),
  });
}

// ── Reports ────────────────────────────────────────────────────────────────────

export function useDailyPumpReport(params: { date: string; outlet?: number }) {
  const qs = new URLSearchParams({ date: params.date });
  if (params.outlet) qs.set("outlet", String(params.outlet));
  return useQuery({
    queryKey: ["fuel-daily-pump-report", params],
    queryFn: () => apiClient<DailyPumpReport>(`/fuel/reports/daily-pump/?${qs}`),
    enabled: !!params.date,
  });
}

export function useVarianceReport(params: {
  date_from: string;
  date_to: string;
  outlet?: number;
}) {
  const qs = new URLSearchParams({
    date_from: params.date_from,
    date_to: params.date_to,
  });
  if (params.outlet) qs.set("outlet", String(params.outlet));
  return useQuery({
    queryKey: ["fuel-variance-report", params],
    queryFn: () => apiClient<VarianceReport>(`/fuel/reports/variance/?${qs}`),
    enabled: !!params.date_from && !!params.date_to,
  });
}
