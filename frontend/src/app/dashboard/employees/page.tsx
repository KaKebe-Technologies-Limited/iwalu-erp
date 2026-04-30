"use client";

import { useState, FormEvent } from "react";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/lib/store/auth";
import {
  useEmployees,
  useCreateEmployee,
  useTerminateEmployee,
  useDepartments,
  useLeaveRequests,
  useLeaveTypes,
  useCreateLeaveRequest,
  useApproveLeave,
  useRejectLeave,
  useAttendance,
  usePayrollPeriods,
  useProcessPayroll,
  useApprovePayroll,
} from "@/lib/hooks/useHR";
import type { Employee, LeaveRequest, PayrollPeriod, Department, Attendance } from "@/lib/types";

// ── Helpers ──────────────────────────────────────────────────────────────────

function today() {
  return new Date().toISOString().split("T")[0];
}

function formatCurrency(value: string | number): string {
  const num = parseFloat(String(value));
  if (isNaN(num)) return "UGX 0";
  if (num >= 1_000_000_000) return `UGX ${(num / 1_000_000_000).toFixed(1)}B`;
  if (num >= 1_000_000) return `UGX ${(num / 1_000_000).toFixed(1)}M`;
  if (num >= 1_000) return `UGX ${(num / 1_000).toFixed(0)}K`;
  return `UGX ${Math.round(num).toLocaleString()}`;
}

const statusColor: Record<string, { bg: string; text: string }> = {
  active: { bg: "bg-emerald-50", text: "text-emerald-700" },
  terminated: { bg: "bg-red-50", text: "text-red-700" },
  suspended: { bg: "bg-amber-50", text: "text-amber-700" },
};

const leaveStatusColor: Record<string, { bg: string; text: string }> = {
  pending: { bg: "bg-amber-50", text: "text-amber-700" },
  approved: { bg: "bg-emerald-50", text: "text-emerald-700" },
  rejected: { bg: "bg-red-50", text: "text-red-600" },
  cancelled: { bg: "bg-gray-100", text: "text-gray-500" },
};

const payrollStatusColor: Record<string, { bg: string; text: string }> = {
  draft: { bg: "bg-gray-100", text: "text-gray-700" },
  processing: { bg: "bg-blue-50", text: "text-blue-700" },
  approved: { bg: "bg-emerald-50", text: "text-emerald-700" },
  paid: { bg: "bg-violet-50", text: "text-violet-700" },
};

// ── Add Employee Modal ────────────────────────────────────────────────────────

function AddEmployeeModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { data: deptsData } = useDepartments();
  const createEmployee = useCreateEmployee();
  const [form, setForm] = useState({
    user_id: "",
    department: "",
    designation: "",
    employment_type: "full_time" as "full_time" | "part_time" | "contract",
    date_hired: today(),
    basic_salary: "",
    nssf_number: "",
    tin_number: "",
    emergency_contact_name: "",
    emergency_contact_phone: "",
  });
  const [formError, setFormError] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError("");
    if (!form.user_id || !form.designation || !form.basic_salary) {
      setFormError("User ID, designation, and salary are required");
      return;
    }
    createEmployee.mutate(
      {
        user_id: parseInt(form.user_id),
        department: form.department ? parseInt(form.department) : undefined,
        designation: form.designation,
        employment_type: form.employment_type,
        date_hired: form.date_hired,
        basic_salary: form.basic_salary,
        nssf_number: form.nssf_number,
        tin_number: form.tin_number,
        emergency_contact_name: form.emergency_contact_name,
        emergency_contact_phone: form.emergency_contact_phone,
      },
      {
        onSuccess: () => onClose(),
        onError: (err: Error) => setFormError(err.message),
      }
    );
  }

  if (!open) return null;
  const depts = deptsData?.results ?? [];

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto p-6 space-y-4 shadow-xl">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold text-gray-900">Add Employee</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">&times;</button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">User ID *</label>
              <input
                type="number"
                value={form.user_id}
                onChange={(e) => setForm({ ...form, user_id: e.target.value })}
                placeholder="System user ID"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Department</label>
              <select
                value={form.department}
                onChange={(e) => setForm({ ...form, department: e.target.value })}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black"
              >
                <option value="">None</option>
                {depts.map((d) => (
                  <option key={d.id} value={d.id}>{d.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Designation *</label>
              <input
                type="text"
                value={form.designation}
                onChange={(e) => setForm({ ...form, designation: e.target.value })}
                placeholder="e.g. Pump Attendant"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Employment Type</label>
              <select
                value={form.employment_type}
                onChange={(e) => setForm({ ...form, employment_type: e.target.value as typeof form.employment_type })}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black"
              >
                <option value="full_time">Full Time</option>
                <option value="part_time">Part Time</option>
                <option value="contract">Contract</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Date Hired</label>
              <input
                type="date"
                value={form.date_hired}
                onChange={(e) => setForm({ ...form, date_hired: e.target.value })}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Basic Salary (UGX) *</label>
              <input
                type="number"
                min="0"
                value={form.basic_salary}
                onChange={(e) => setForm({ ...form, basic_salary: e.target.value })}
                placeholder="e.g. 800000"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">NSSF Number</label>
              <input
                type="text"
                value={form.nssf_number}
                onChange={(e) => setForm({ ...form, nssf_number: e.target.value })}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">TIN Number</label>
              <input
                type="text"
                value={form.tin_number}
                onChange={(e) => setForm({ ...form, tin_number: e.target.value })}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Emergency Contact</label>
              <input
                type="text"
                value={form.emergency_contact_name}
                onChange={(e) => setForm({ ...form, emergency_contact_name: e.target.value })}
                placeholder="Name"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Emergency Phone</label>
              <input
                type="text"
                value={form.emergency_contact_phone}
                onChange={(e) => setForm({ ...form, emergency_contact_phone: e.target.value })}
                placeholder="+256 7XX XXX XXX"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black"
              />
            </div>
          </div>

          {formError && <p className="text-sm text-red-600 font-medium">{formError}</p>}

          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 rounded-lg border border-gray-200 text-sm font-semibold text-gray-700 hover:bg-gray-50">
              Cancel
            </button>
            <button
              type="submit"
              disabled={createEmployee.isPending}
              className="px-4 py-2 rounded-lg bg-black text-white text-sm font-semibold hover:bg-zinc-800 disabled:opacity-50"
            >
              {createEmployee.isPending ? "Adding…" : "Add Employee"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── New Leave Request Modal ────────────────────────────────────────────────────

function NewLeaveModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { data: typesData } = useLeaveTypes();
  const createLeave = useCreateLeaveRequest();
  const [form, setForm] = useState({
    leave_type: "",
    start_date: today(),
    end_date: today(),
    days_requested: "1",
    reason: "",
  });
  const [formError, setFormError] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError("");
    if (!form.leave_type) {
      setFormError("Please select a leave type");
      return;
    }
    createLeave.mutate(
      {
        leave_type: parseInt(form.leave_type),
        start_date: form.start_date,
        end_date: form.end_date,
        days_requested: form.days_requested,
        reason: form.reason,
      },
      {
        onSuccess: () => onClose(),
        onError: (err: Error) => setFormError(err.message),
      }
    );
  }

  if (!open) return null;
  const leaveTypes = typesData?.results ?? [];

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl w-full max-w-md p-6 space-y-4 shadow-xl">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold text-gray-900">New Leave Request</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">&times;</button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1">Leave Type *</label>
            <select
              value={form.leave_type}
              onChange={(e) => setForm({ ...form, leave_type: e.target.value })}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black"
            >
              <option value="">Select type…</option>
              {leaveTypes.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">Start Date</label>
              <input
                type="date"
                value={form.start_date}
                onChange={(e) => setForm({ ...form, start_date: e.target.value })}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">End Date</label>
              <input
                type="date"
                value={form.end_date}
                onChange={(e) => setForm({ ...form, end_date: e.target.value })}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1">Days Requested</label>
            <input
              type="number"
              min="0.5"
              step="0.5"
              value={form.days_requested}
              onChange={(e) => setForm({ ...form, days_requested: e.target.value })}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1">Reason (optional)</label>
            <textarea
              value={form.reason}
              onChange={(e) => setForm({ ...form, reason: e.target.value })}
              rows={3}
              placeholder="Brief reason for the leave…"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black resize-none"
            />
          </div>

          {formError && <p className="text-sm text-red-600 font-medium">{formError}</p>}

          <div className="flex gap-3 justify-end pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 rounded-lg border border-gray-200 text-sm font-semibold text-gray-700 hover:bg-gray-50">
              Cancel
            </button>
            <button
              type="submit"
              disabled={createLeave.isPending}
              className="px-4 py-2 rounded-lg bg-black text-white text-sm font-semibold hover:bg-zinc-800 disabled:opacity-50"
            >
              {createLeave.isPending ? "Submitting…" : "Submit Request"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function EmployeesPage() {
  const user = useAuthStore((s) => s.user);
  const isManager = user?.role === "admin" || user?.role === "manager";

  const [activeView, setActiveView] = useState<"directory" | "attendance" | "leave" | "payroll">("directory");
  const [searchQuery, setSearchQuery] = useState("");
  const [filterStatus, setFilterStatus] = useState<string>("active");
  const [leaveFilter, setLeaveFilter] = useState<string>("");
  const [showAddEmployee, setShowAddEmployee] = useState(false);
  const [showNewLeave, setShowNewLeave] = useState(false);

  const { data: employeesData, isLoading: empLoading } = useEmployees({
    search: searchQuery || undefined,
    status: filterStatus || undefined,
  });
  const { data: deptsData } = useDepartments();
  const { data: leaveData, isLoading: leaveLoading } = useLeaveRequests({
    status: leaveFilter || undefined,
  });
  const { data: attendanceData } = useAttendance({ date_from: today(), date_to: today() });
  const { data: payrollData } = usePayrollPeriods();

  const approveLeave = useApproveLeave();
  const rejectLeave = useRejectLeave();
  const terminateEmployee = useTerminateEmployee();
  const processPayroll = useProcessPayroll();
  const approvePayroll = useApprovePayroll();

  const employees = employeesData?.results ?? [];
  const departments = deptsData?.results ?? [];
  const leaveRequests = leaveData?.results ?? [];
  const attendance = attendanceData?.results ?? [];
  const payrollPeriods = payrollData?.results ?? [];
  const latestPayroll = payrollPeriods[0] ?? null;

  const pendingLeaveCount = leaveData
    ? leaveRequests.filter((r) => r.status === "pending").length
    : 0;

  return (
    <>
      <AddEmployeeModal open={showAddEmployee} onClose={() => setShowAddEmployee(false)} />
      <NewLeaveModal open={showNewLeave} onClose={() => setShowNewLeave(false)} />

      <div className="space-y-6 max-w-[1400px]">
        {/* Header */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight">Employees</h1>
            <p className="text-sm text-gray-500 mt-1">Staff directory, attendance, leave, and payroll</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowNewLeave(true)}
              className="px-4 py-2.5 rounded-xl border border-gray-200 text-black text-sm font-semibold hover:bg-gray-50 transition-all"
            >
              Request Leave
            </button>
            {isManager && (
              <button
                onClick={() => setShowAddEmployee(true)}
                className="px-4 py-2.5 rounded-xl bg-black text-white text-sm font-semibold hover:bg-zinc-800 transition-all shadow-sm"
              >
                + Add Employee
              </button>
            )}
          </div>
        </div>

        {/* View Tabs */}
        <div className="flex gap-1 bg-gray-100 p-1 rounded-xl w-fit">
          {([
            { id: "directory", label: "Directory" },
            { id: "attendance", label: "Attendance" },
            { id: "leave", label: "Leave Management" },
            { id: "payroll", label: "Payroll" },
          ] as const).map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveView(tab.id)}
              className={cn(
                "px-4 py-2.5 rounded-lg text-sm font-semibold whitespace-nowrap transition-all",
                activeView === tab.id ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
              )}
            >
              {tab.label}
              {tab.id === "leave" && pendingLeaveCount > 0 && (
                <span className="ml-1.5 px-1.5 py-0.5 rounded-full bg-amber-500 text-white text-xs font-bold">
                  {pendingLeaveCount}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white rounded-2xl p-5 border border-gray-100 shadow-sm">
            <p className="text-sm font-medium text-gray-500">Total Employees</p>
            <p className="text-2xl font-extrabold text-gray-900 mt-1">{employeesData?.count ?? "—"}</p>
            <p className="text-xs text-gray-400 mt-1">{filterStatus || "All"} status</p>
          </div>
          <div className="bg-white rounded-2xl p-5 border border-gray-100 shadow-sm">
            <p className="text-sm font-medium text-gray-500">Departments</p>
            <p className="text-2xl font-extrabold text-gray-900 mt-1">{departments.length}</p>
            <p className="text-xs text-gray-400 mt-1">Active departments</p>
          </div>
          <div className="bg-white rounded-2xl p-5 border border-gray-100 shadow-sm">
            <p className="text-sm font-medium text-gray-500">Today Clocked In</p>
            <p className="text-2xl font-extrabold text-gray-900 mt-1">
              {attendance.filter((a) => a.clock_in).length}
            </p>
            <p className="text-xs text-gray-400 mt-1">Attendance records</p>
          </div>
          <div className="bg-white rounded-2xl p-5 border border-gray-100 shadow-sm">
            <p className="text-sm font-medium text-gray-500">Pending Leave</p>
            <p className="text-2xl font-extrabold text-gray-900 mt-1">{pendingLeaveCount}</p>
            <p className="text-xs text-gray-400 mt-1">Awaiting approval</p>
          </div>
        </div>

        {/* Tab Content */}
        {activeView === "directory" && (
          <DirectoryView
            employees={employees}
            isLoading={empLoading}
            departments={departments}
            searchQuery={searchQuery}
            setSearchQuery={setSearchQuery}
            filterStatus={filterStatus}
            setFilterStatus={setFilterStatus}
            isManager={isManager}
            onTerminate={(id) => terminateEmployee.mutate(id)}
          />
        )}
        {activeView === "attendance" && <AttendanceView records={attendance} />}
        {activeView === "leave" && (
          <LeaveView
            requests={leaveRequests}
            isLoading={leaveLoading}
            leaveFilter={leaveFilter}
            setLeaveFilter={setLeaveFilter}
            isManager={isManager}
            onApprove={(id) => approveLeave.mutate(id)}
            onReject={(id) => rejectLeave.mutate({ id })}
          />
        )}
        {activeView === "payroll" && (
          <PayrollView
            periods={payrollPeriods}
            isManager={isManager}
            onProcess={(id) => processPayroll.mutate(id)}
            onApprove={(id) => approvePayroll.mutate(id)}
          />
        )}

        {/* Payroll Summary Banner */}
        {latestPayroll && (
          <PayrollBanner period={latestPayroll} isManager={isManager} onProcess={(id) => processPayroll.mutate(id)} onApprove={(id) => approvePayroll.mutate(id)} />
        )}
      </div>
    </>
  );
}

// ── Directory View ────────────────────────────────────────────────────────────

function DirectoryView({
  employees,
  isLoading,
  departments,
  searchQuery,
  setSearchQuery,
  filterStatus,
  setFilterStatus,
  isManager,
  onTerminate,
}: {
  employees: Employee[];
  isLoading: boolean;
  departments: Department[];
  searchQuery: string;
  setSearchQuery: (v: string) => void;
  filterStatus: string;
  setFilterStatus: (v: string) => void;
  isManager: boolean;
  onTerminate: (id: number) => void;
}) {
  return (
    <>
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <h2 className="text-lg font-bold text-gray-900">Staff Directory</h2>
          <div className="flex items-center gap-3">
            <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
              {["active", "terminated", "suspended", ""].map((f) => (
                <button
                  key={f}
                  onClick={() => setFilterStatus(f)}
                  className={cn(
                    "px-3 py-1.5 rounded-md text-xs font-semibold transition-all",
                    filterStatus === f ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
                  )}
                >
                  {f === "" ? "All" : f.charAt(0).toUpperCase() + f.slice(1)}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2 bg-gray-100 rounded-lg px-3 py-2">
              <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="text"
                placeholder="Search employees…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="bg-transparent text-sm outline-none placeholder-gray-400 w-40"
              />
            </div>
          </div>
        </div>
        {isLoading ? (
          <p className="px-6 py-8 text-sm text-gray-400 text-center">Loading employees…</p>
        ) : employees.length === 0 ? (
          <p className="px-6 py-8 text-sm text-gray-400 italic text-center">No employees found</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50">
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Employee</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Designation</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Department</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Outlet</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Hired</th>
                  <th className="text-center px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Status</th>
                  {isManager && <th className="text-center px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {employees.map((emp) => {
                  const sc = statusColor[emp.employment_status] ?? statusColor.active;
                  return (
                    <tr key={emp.id} className="hover:bg-gray-50/50 transition-colors">
                      <td className="px-6 py-3">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-black text-white flex items-center justify-center text-xs font-bold flex-shrink-0">
                            {emp.employee_number.slice(-2)}
                          </div>
                          <div>
                            <p className="font-semibold text-gray-900">{emp.designation || "—"}</p>
                            <p className="text-xs text-gray-400">{emp.employee_number}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-3 text-gray-600">{emp.designation}</td>
                      <td className="px-6 py-3 text-gray-600">{emp.department_name ?? "—"}</td>
                      <td className="px-6 py-3 text-gray-600">{emp.outlet_name ?? "—"}</td>
                      <td className="px-6 py-3 text-gray-500 text-xs">{emp.date_hired}</td>
                      <td className="px-6 py-3 text-center">
                        <span className={cn("px-2.5 py-1 rounded-full text-xs font-semibold capitalize", sc.bg, sc.text)}>
                          {emp.employment_status}
                        </span>
                      </td>
                      {isManager && (
                        <td className="px-6 py-3 text-center">
                          {emp.employment_status === "active" && (
                            <button
                              onClick={() => {
                                if (confirm(`Terminate ${emp.employee_number}?`)) onTerminate(emp.id);
                              }}
                              className="px-2.5 py-1 rounded-lg bg-red-50 text-red-600 text-xs font-semibold hover:bg-red-100 transition-colors"
                            >
                              Terminate
                            </button>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Departments */}
      {departments.length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <h2 className="text-lg font-bold text-gray-900 mb-5">Departments</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {departments.map((dept) => (
              <div key={dept.id} className="rounded-xl bg-gray-50 p-4 hover:bg-gray-100 transition-colors">
                <p className="text-sm font-bold text-gray-900">{dept.name}</p>
                <p className="text-2xl font-extrabold text-gray-900 mt-1">{dept.employee_count}</p>
                <p className="text-xs text-gray-400 mt-1">Active employees</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

// ── Attendance View ───────────────────────────────────────────────────────────

function AttendanceView({ records }: { records: Attendance[] }) {
  const checkedIn = records.filter((r) => r.clock_in && !r.clock_out).length;
  const completed = records.filter((r) => r.clock_in && r.clock_out).length;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-xl bg-gray-50 p-4">
          <p className="text-xs text-gray-500 font-medium mb-1">Total Records Today</p>
          <p className="text-2xl font-extrabold text-gray-900">{records.length}</p>
        </div>
        <div className="rounded-xl bg-emerald-50 p-4">
          <p className="text-xs text-emerald-700 font-medium mb-1">Currently In</p>
          <p className="text-2xl font-extrabold text-gray-900">{checkedIn}</p>
        </div>
        <div className="rounded-xl bg-blue-50 p-4">
          <p className="text-xs text-blue-700 font-medium mb-1">Completed Shifts</p>
          <p className="text-2xl font-extrabold text-gray-900">{completed}</p>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-900">Today&apos;s Attendance — {today()}</h2>
        </div>
        {records.length === 0 ? (
          <p className="px-6 py-8 text-sm text-gray-400 italic text-center">No attendance records for today</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50">
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Employee</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Clock In</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Clock Out</th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Hours</th>
                  <th className="text-center px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {records.map((rec) => (
                  <tr key={rec.id} className="hover:bg-gray-50/50 transition-colors">
                    <td className="px-6 py-3 font-semibold text-gray-900">{rec.employee_number}</td>
                    <td className="px-6 py-3 text-gray-600">
                      {rec.clock_in ? new Date(rec.clock_in).toLocaleTimeString() : "—"}
                    </td>
                    <td className="px-6 py-3 text-gray-600">
                      {rec.clock_out ? new Date(rec.clock_out).toLocaleTimeString() : "—"}
                    </td>
                    <td className="px-6 py-3 text-right font-semibold text-gray-900">
                      {rec.hours_worked > 0 ? `${rec.hours_worked.toFixed(1)}h` : "—"}
                    </td>
                    <td className="px-6 py-3 text-center">
                      <span className={cn(
                        "px-2.5 py-1 rounded-full text-xs font-semibold",
                        rec.clock_out ? "bg-blue-50 text-blue-700" : rec.clock_in ? "bg-emerald-50 text-emerald-700" : "bg-gray-100 text-gray-600"
                      )}>
                        {rec.clock_out ? "Completed" : rec.clock_in ? "In" : "Absent"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Leave View ────────────────────────────────────────────────────────────────

function LeaveView({
  requests,
  isLoading,
  leaveFilter,
  setLeaveFilter,
  isManager,
  onApprove,
  onReject,
}: {
  requests: LeaveRequest[];
  isLoading: boolean;
  leaveFilter: string;
  setLeaveFilter: (v: string) => void;
  isManager: boolean;
  onApprove: (id: number) => void;
  onReject: (id: number) => void;
}) {
  return (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <h2 className="text-lg font-bold text-gray-900">Leave Requests</h2>
          <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
            {["", "pending", "approved", "rejected"].map((f) => (
              <button
                key={f}
                onClick={() => setLeaveFilter(f)}
                className={cn(
                  "px-3 py-1.5 rounded-md text-xs font-semibold transition-all",
                  leaveFilter === f ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
                )}
              >
                {f === "" ? "All" : f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
          </div>
        </div>
        {isLoading ? (
          <p className="px-6 py-8 text-sm text-gray-400 text-center">Loading leave requests…</p>
        ) : requests.length === 0 ? (
          <p className="px-6 py-8 text-sm text-gray-400 italic text-center">No leave requests found</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50">
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Employee</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Type</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">From</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">To</th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Days</th>
                  <th className="text-center px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Status</th>
                  {isManager && <th className="text-center px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {requests.map((req) => {
                  const sc = leaveStatusColor[req.status] ?? leaveStatusColor.pending;
                  return (
                    <tr key={req.id} className="hover:bg-gray-50/50 transition-colors">
                      <td className="px-6 py-3 font-semibold text-gray-900">{req.employee_number}</td>
                      <td className="px-6 py-3">
                        <span className="px-2 py-1 rounded-md bg-blue-50 text-blue-700 text-xs font-medium">
                          {req.leave_type_name}
                        </span>
                      </td>
                      <td className="px-6 py-3 text-gray-600">{req.start_date}</td>
                      <td className="px-6 py-3 text-gray-600">{req.end_date}</td>
                      <td className="px-6 py-3 text-right font-bold text-gray-900">{req.days_requested}</td>
                      <td className="px-6 py-3 text-center">
                        <span className={cn("px-2.5 py-1 rounded-full text-xs font-semibold capitalize", sc.bg, sc.text)}>
                          {req.status}
                        </span>
                      </td>
                      {isManager && (
                        <td className="px-6 py-3 text-center">
                          {req.status === "pending" && (
                            <div className="flex items-center justify-center gap-2">
                              <button
                                onClick={() => onApprove(req.id)}
                                className="px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-700 text-xs font-semibold hover:bg-emerald-100 transition-colors"
                              >
                                Approve
                              </button>
                              <button
                                onClick={() => onReject(req.id)}
                                className="px-2.5 py-1 rounded-lg bg-red-50 text-red-600 text-xs font-semibold hover:bg-red-100 transition-colors"
                              >
                                Reject
                              </button>
                            </div>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Payroll View ──────────────────────────────────────────────────────────────

function PayrollView({
  periods,
  isManager,
  onProcess,
  onApprove,
}: {
  periods: PayrollPeriod[];
  isManager: boolean;
  onProcess: (id: number) => void;
  onApprove: (id: number) => void;
}) {
  return (
    <div className="space-y-4">
      {periods.length === 0 ? (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-8 text-center">
          <p className="text-sm text-gray-400 italic">No payroll periods created yet</p>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="text-lg font-bold text-gray-900">Payroll Periods</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50">
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Period</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Dates</th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Gross</th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Deductions</th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Net Pay</th>
                  <th className="text-center px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Status</th>
                  {isManager && <th className="text-center px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Actions</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {periods.map((p) => {
                  const pc = payrollStatusColor[p.status] ?? payrollStatusColor.draft;
                  return (
                    <tr key={p.id} className="hover:bg-gray-50/50 transition-colors">
                      <td className="px-6 py-3 font-semibold text-gray-900">{p.name}</td>
                      <td className="px-6 py-3 text-gray-500 text-xs">{p.start_date} → {p.end_date}</td>
                      <td className="px-6 py-3 text-right text-gray-700">{formatCurrency(p.total_gross)}</td>
                      <td className="px-6 py-3 text-right text-gray-700">{formatCurrency(p.total_deductions)}</td>
                      <td className="px-6 py-3 text-right font-bold text-gray-900">{formatCurrency(p.total_net)}</td>
                      <td className="px-6 py-3 text-center">
                        <span className={cn("px-2.5 py-1 rounded-full text-xs font-semibold capitalize", pc.bg, pc.text)}>
                          {p.status}
                        </span>
                      </td>
                      {isManager && (
                        <td className="px-6 py-3 text-center">
                          <div className="flex items-center justify-center gap-2">
                            {p.status === "draft" && (
                              <button
                                onClick={() => onProcess(p.id)}
                                className="px-2.5 py-1 rounded-lg bg-blue-50 text-blue-700 text-xs font-semibold hover:bg-blue-100"
                              >
                                Process
                              </button>
                            )}
                            {p.status === "processing" && (
                              <button
                                onClick={() => onApprove(p.id)}
                                className="px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-700 text-xs font-semibold hover:bg-emerald-100"
                              >
                                Approve
                              </button>
                            )}
                          </div>
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Payroll Banner ────────────────────────────────────────────────────────────

function PayrollBanner({
  period,
  isManager,
  onProcess,
  onApprove,
}: {
  period: PayrollPeriod;
  isManager: boolean;
  onProcess: (id: number) => void;
  onApprove: (id: number) => void;
}) {
  return (
    <div className="bg-gradient-to-br from-gray-900 to-black rounded-2xl p-6 text-white">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold">{period.name} Payroll</h2>
          <p className="text-gray-400 text-sm mt-1">
            {period.start_date} → {period.end_date} · {period.pay_slips_count} pay slips
          </p>
        </div>
        <div className="flex items-center gap-6">
          <div>
            <p className="text-gray-400 text-xs font-medium uppercase tracking-wider">Gross</p>
            <p className="text-xl font-extrabold">{formatCurrency(period.total_gross)}</p>
          </div>
          <div>
            <p className="text-gray-400 text-xs font-medium uppercase tracking-wider">Deductions</p>
            <p className="text-xl font-extrabold">{formatCurrency(period.total_deductions)}</p>
          </div>
          <div>
            <p className="text-gray-400 text-xs font-medium uppercase tracking-wider">Net Pay</p>
            <p className="text-xl font-extrabold text-emerald-400">{formatCurrency(period.total_net)}</p>
          </div>
          {isManager && period.status === "draft" && (
            <button
              onClick={() => onProcess(period.id)}
              className="px-4 py-2 rounded-lg bg-white text-black text-sm font-semibold hover:bg-gray-100 transition-colors"
            >
              Process
            </button>
          )}
          {isManager && period.status === "processing" && (
            <button
              onClick={() => onApprove(period.id)}
              className="px-4 py-2 rounded-lg bg-emerald-500 text-white text-sm font-semibold hover:bg-emerald-600 transition-colors"
            >
              Approve
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
