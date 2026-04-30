'use client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api';
import type {
  PaginatedResponse,
  Department,
  Employee,
  LeaveType,
  LeaveBalance,
  LeaveRequest,
  Attendance,
  PayrollPeriod,
  PaySlip,
} from '../types';

// ─── Departments ──────────────────────────────────────────────────────────────

export function useDepartments(params: { outlet?: number; is_active?: boolean } = {}) {
  return useQuery<PaginatedResponse<Department>>({
    queryKey: ['departments', params],
    queryFn: () => {
      const query = new URLSearchParams();
      if (params.outlet) query.append('outlet', String(params.outlet));
      if (params.is_active !== undefined) query.append('is_active', String(params.is_active));
      return apiClient(`/departments/?${query.toString()}`);
    },
  });
}

// ─── Employees ────────────────────────────────────────────────────────────────

export function useEmployees(params: {
  search?: string;
  department?: number;
  status?: string;
  page?: number;
} = {}) {
  return useQuery<PaginatedResponse<Employee>>({
    queryKey: ['employees', params],
    queryFn: () => {
      const query = new URLSearchParams();
      if (params.search) query.append('search', params.search);
      if (params.department) query.append('department', String(params.department));
      if (params.status) query.append('status', params.status);
      if (params.page) query.append('page', String(params.page));
      return apiClient(`/employees/?${query.toString()}`);
    },
  });
}

export function useCreateEmployee() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Employee>) =>
      apiClient('/employees/', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['employees'] }),
  });
}

export function useUpdateEmployee() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: Partial<Employee> & { id: number }) =>
      apiClient(`/employees/${id}/`, { method: 'PATCH', body: JSON.stringify(data) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['employees'] }),
  });
}

export function useTerminateEmployee() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiClient(`/employees/${id}/terminate/`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['employees'] }),
  });
}

// ─── Leave Types ──────────────────────────────────────────────────────────────

export function useLeaveTypes() {
  return useQuery<PaginatedResponse<LeaveType>>({
    queryKey: ['leave-types'],
    queryFn: () => apiClient('/leave-types/'),
  });
}

// ─── Leave Balances ───────────────────────────────────────────────────────────

export function useLeaveBalances(params: { employee?: number; year?: number } = {}) {
  return useQuery<PaginatedResponse<LeaveBalance>>({
    queryKey: ['leave-balances', params],
    queryFn: () => {
      const query = new URLSearchParams();
      if (params.employee) query.append('employee', String(params.employee));
      if (params.year) query.append('year', String(params.year));
      return apiClient(`/leave-balances/?${query.toString()}`);
    },
  });
}

// ─── Leave Requests ───────────────────────────────────────────────────────────

export function useLeaveRequests(params: { status?: string; page?: number } = {}) {
  return useQuery<PaginatedResponse<LeaveRequest>>({
    queryKey: ['leave-requests', params],
    queryFn: () => {
      const query = new URLSearchParams();
      if (params.status) query.append('status', params.status);
      if (params.page) query.append('page', String(params.page));
      return apiClient(`/leave-requests/?${query.toString()}`);
    },
  });
}

export function useCreateLeaveRequest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      leave_type: number;
      start_date: string;
      end_date: string;
      days_requested: string;
      reason?: string;
    }) =>
      apiClient('/leave-requests/', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['leave-requests'] }),
  });
}

export function useApproveLeave() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiClient(`/leave-requests/${id}/approve/`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['leave-requests'] }),
  });
}

export function useRejectLeave() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: number; reason?: string }) =>
      apiClient(`/leave-requests/${id}/reject/`, {
        method: 'POST',
        body: JSON.stringify({ reason: reason || '' }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['leave-requests'] }),
  });
}

export function useCancelLeave() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiClient(`/leave-requests/${id}/cancel/`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['leave-requests'] }),
  });
}

// ─── Attendance ───────────────────────────────────────────────────────────────

export function useAttendance(params: {
  employee?: number;
  outlet?: number;
  date_from?: string;
  date_to?: string;
  page?: number;
} = {}) {
  return useQuery<PaginatedResponse<Attendance>>({
    queryKey: ['attendance', params],
    queryFn: () => {
      const query = new URLSearchParams();
      if (params.employee) query.append('employee', String(params.employee));
      if (params.outlet) query.append('outlet', String(params.outlet));
      if (params.date_from) query.append('date_from', params.date_from);
      if (params.date_to) query.append('date_to', params.date_to);
      if (params.page) query.append('page', String(params.page));
      return apiClient(`/attendance/?${query.toString()}`);
    },
  });
}

export function useClockIn() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (outlet_id?: number) =>
      apiClient('/attendance/clock-in/', {
        method: 'POST',
        body: JSON.stringify({ outlet_id: outlet_id ?? null }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['attendance'] }),
  });
}

export function useClockOut() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient('/attendance/clock-out/', { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['attendance'] }),
  });
}

// ─── Payroll ──────────────────────────────────────────────────────────────────

export function usePayrollPeriods(params: { status?: string; page?: number } = {}) {
  return useQuery<PaginatedResponse<PayrollPeriod>>({
    queryKey: ['payroll-periods', params],
    queryFn: () => {
      const query = new URLSearchParams();
      if (params.status) query.append('status', params.status);
      if (params.page) query.append('page', String(params.page));
      return apiClient(`/payroll-periods/?${query.toString()}`);
    },
  });
}

export function useCreatePayrollPeriod() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; start_date: string; end_date: string }) =>
      apiClient('/payroll-periods/', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['payroll-periods'] }),
  });
}

export function useProcessPayroll() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiClient(`/payroll-periods/${id}/process/`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['payroll-periods'] }),
  });
}

export function useApprovePayroll() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiClient(`/payroll-periods/${id}/approve/`, { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['payroll-periods'] }),
  });
}

export function usePaySlips(params: {
  employee?: number;
  payroll_period?: number;
  page?: number;
} = {}) {
  return useQuery<PaginatedResponse<PaySlip>>({
    queryKey: ['pay-slips', params],
    queryFn: () => {
      const query = new URLSearchParams();
      if (params.employee) query.append('employee', String(params.employee));
      if (params.payroll_period) query.append('payroll_period', String(params.payroll_period));
      if (params.page) query.append('page', String(params.page));
      return apiClient(`/pay-slips/?${query.toString()}`);
    },
  });
}
