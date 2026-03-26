"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

// ── Mock data ───────────────────────────────────────────────────────────────

const hrKPIs = [
  { label: "Total Employees", value: "52", sub: "Active on payroll", color: "emerald" },
  { label: "On Duty Today", value: "47", sub: "90.4% attendance", color: "blue" },
  { label: "On Leave", value: "3", sub: "2 annual, 1 sick", color: "amber" },
  { label: "Open Positions", value: "2", sub: "Pump Attendant, Cashier", color: "violet" },
];

const employees = [
  { id: "EMP-001", name: "Sarah Nakamya", email: "sarah@nexus.com", role: "Station Manager", department: "Operations", branch: "Main Branch", phone: "+256 700 111 001", status: "On Duty", shift: "Morning", joined: "15 Jan 2024", salary: "UGX 1.8M" },
  { id: "EMP-002", name: "Peter Ouma", email: "peter@nexus.com", role: "Cashier", department: "POS", branch: "Main Branch", phone: "+256 700 111 002", status: "On Duty", shift: "Morning", joined: "1 Mar 2024", salary: "UGX 800K" },
  { id: "EMP-003", name: "Grace Achieng", email: "grace@nexus.com", role: "Pump Attendant", department: "Fuel", branch: "Lira Branch", phone: "+256 700 111 003", status: "On Duty", shift: "Morning", joined: "10 Feb 2024", salary: "UGX 650K" },
  { id: "EMP-004", name: "David Ssali", email: "david@nexus.com", role: "Accountant", department: "Finance", branch: "Head Office", phone: "+256 700 111 004", status: "On Leave", shift: "—", joined: "1 Jan 2024", salary: "UGX 1.5M" },
  { id: "EMP-005", name: "Janet Adong", email: "janet@nexus.com", role: "Pump Attendant", department: "Fuel", branch: "Main Branch", phone: "+256 700 111 005", status: "Off Duty", shift: "Evening", joined: "15 Apr 2024", salary: "UGX 650K" },
  { id: "EMP-006", name: "Moses Kato", email: "moses@nexus.com", role: "Store Keeper", department: "Inventory", branch: "Lira Branch", phone: "+256 700 111 006", status: "On Duty", shift: "Morning", joined: "20 Feb 2024", salary: "UGX 750K" },
  { id: "EMP-007", name: "Rita Nambi", email: "rita@nexus.com", role: "Cashier", department: "POS", branch: "Lira Branch", phone: "+256 700 111 007", status: "On Duty", shift: "Morning", joined: "5 May 2024", salary: "UGX 800K" },
  { id: "EMP-008", name: "Isaac Okello", email: "isaac@nexus.com", role: "Pump Attendant", department: "Fuel", branch: "Main Branch", phone: "+256 700 111 008", status: "On Duty", shift: "Morning", joined: "12 Jun 2024", salary: "UGX 650K" },
  { id: "EMP-009", name: "Florence Aber", email: "florence@nexus.com", role: "HR Officer", department: "HR", branch: "Head Office", phone: "+256 700 111 009", status: "On Leave", shift: "—", joined: "1 Jan 2024", salary: "UGX 1.2M" },
  { id: "EMP-010", name: "Charles Odongo", email: "charles@nexus.com", role: "Security Guard", department: "Operations", branch: "Main Branch", phone: "+256 700 111 010", status: "On Duty", shift: "Night", joined: "8 Mar 2024", salary: "UGX 500K" },
];

const leaveRequests = [
  { employee: "David Ssali", type: "Annual Leave", from: "1 Mar 2026", to: "7 Mar 2026", days: 5, status: "Approved", approver: "Sarah Nakamya" },
  { employee: "Florence Aber", type: "Sick Leave", from: "2 Mar 2026", to: "4 Mar 2026", days: 3, status: "Approved", approver: "Sarah Nakamya" },
  { employee: "Peter Ouma", type: "Annual Leave", from: "10 Mar 2026", to: "14 Mar 2026", days: 5, status: "Pending", approver: "—" },
  { employee: "Grace Achieng", type: "Maternity", from: "1 Apr 2026", to: "30 Jun 2026", days: 90, status: "Pending", approver: "—" },
];

const attendanceSummary = [
  { shift: "Morning (6AM–2PM)", scheduled: 18, present: 17, absent: 1, color: "bg-amber-500" },
  { shift: "Afternoon (2PM–10PM)", scheduled: 16, present: 16, absent: 0, color: "bg-blue-500" },
  { shift: "Night (10PM–6AM)", scheduled: 8, present: 8, absent: 0, color: "bg-violet-500" },
];

const departments = [
  { name: "Operations", count: 12, head: "Sarah Nakamya" },
  { name: "Fuel", count: 16, head: "Grace Achieng (Acting)" },
  { name: "POS / Retail", count: 8, head: "Peter Ouma (Acting)" },
  { name: "Finance", count: 4, head: "David Ssali" },
  { name: "Inventory", count: 6, head: "Moses Kato" },
  { name: "HR", count: 3, head: "Florence Aber" },
  { name: "Security", count: 3, head: "Charles Odongo" },
];

const dutyColor: Record<string, { bg: string; text: string }> = {
  "On Duty": { bg: "bg-emerald-50", text: "text-emerald-700" },
  "Off Duty": { bg: "bg-gray-100", text: "text-gray-600" },
  "On Leave": { bg: "bg-amber-50", text: "text-amber-700" },
};

const colorMap: Record<string, { bg: string; text: string; light: string }> = {
  emerald: { bg: "bg-emerald-500", text: "text-emerald-600", light: "bg-emerald-50" },
  blue: { bg: "bg-blue-500", text: "text-blue-600", light: "bg-blue-50" },
  violet: { bg: "bg-violet-500", text: "text-violet-600", light: "bg-violet-50" },
  amber: { bg: "bg-amber-500", text: "text-amber-600", light: "bg-amber-50" },
};

// ── Component ───────────────────────────────────────────────────────────────

export default function EmployeesPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [activeView, setActiveView] = useState<"directory" | "attendance" | "leave">("directory");
  const [filterStatus, setFilterStatus] = useState<"all" | "On Duty" | "Off Duty" | "On Leave">("all");

  const filteredEmployees = employees.filter((emp) => {
    const matchSearch = emp.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      emp.role.toLowerCase().includes(searchQuery.toLowerCase()) ||
      emp.department.toLowerCase().includes(searchQuery.toLowerCase()) ||
      emp.id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchFilter = filterStatus === "all" || emp.status === filterStatus;
    return matchSearch && matchFilter;
  });

  return (
    <div className="space-y-6 max-w-[1400px]">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight">
            Employees
          </h1>
          <p className="text-sm text-gray-500 mt-1">Staff directory, attendance, and leave management</p>
        </div>
        <button className="px-4 py-2.5 rounded-xl bg-black text-white text-sm font-semibold hover:bg-zinc-800 transition-all shadow-sm">
          + Add Employee
        </button>
      </div>

      {/* View Tabs */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-xl w-fit">
        {([
          { id: "directory", label: "Directory" },
          { id: "attendance", label: "Attendance" },
          { id: "leave", label: "Leave Management" },
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
          </button>
        ))}
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {hrKPIs.map((stat) => {
          const c = colorMap[stat.color];
          return (
            <div key={stat.label} className="bg-white rounded-2xl p-5 border border-gray-100 shadow-sm hover:shadow-md transition-shadow">
              <p className="text-sm font-medium text-gray-500">{stat.label}</p>
              <p className="text-2xl font-extrabold text-gray-900 mt-1">{stat.value}</p>
              <p className="text-xs text-gray-400 mt-1">{stat.sub}</p>
              <div className={cn("mt-3 h-1 rounded-full", c.light)}>
                <div className={cn("h-1 rounded-full", c.bg)} style={{ width: "65%" }} />
              </div>
            </div>
          );
        })}
      </div>

      {activeView === "directory" && (
        <>
          {/* Employee Table */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <h2 className="text-lg font-bold text-gray-900">Staff Directory</h2>
              <div className="flex items-center gap-3">
                <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
                  {(["all", "On Duty", "Off Duty", "On Leave"] as const).map((f) => (
                    <button
                      key={f}
                      onClick={() => setFilterStatus(f)}
                      className={cn(
                        "px-3 py-1.5 rounded-md text-xs font-semibold transition-all",
                        filterStatus === f ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
                      )}
                    >
                      {f === "all" ? "All" : f}
                    </button>
                  ))}
                </div>
                <div className="flex items-center gap-2 bg-gray-100 rounded-lg px-3 py-2">
                  <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  <input
                    type="text"
                    placeholder="Search employees..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="bg-transparent text-sm outline-none placeholder-gray-400 w-40"
                  />
                </div>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50">
                    <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Employee</th>
                    <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Role</th>
                    <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Department</th>
                    <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Branch</th>
                    <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Shift</th>
                    <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {filteredEmployees.map((emp) => {
                    const dc = dutyColor[emp.status] || { bg: "bg-gray-100", text: "text-gray-600" };
                    return (
                      <tr key={emp.id} className="hover:bg-gray-50/50 transition-colors">
                        <td className="px-6 py-3">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-black text-white flex items-center justify-center text-xs font-bold flex-shrink-0">
                              {emp.name.split(" ").map((n) => n[0]).join("")}
                            </div>
                            <div>
                              <span className="font-semibold text-gray-900">{emp.name}</span>
                              <p className="text-xs text-gray-400">{emp.id}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-3 text-gray-600">{emp.role}</td>
                        <td className="px-6 py-3 text-gray-600">{emp.department}</td>
                        <td className="px-6 py-3 text-gray-600">{emp.branch}</td>
                        <td className="px-6 py-3 text-gray-600">{emp.shift}</td>
                        <td className="px-6 py-3">
                          <span className={cn("px-2.5 py-1 rounded-full text-xs font-semibold", dc.bg, dc.text)}>
                            {emp.status}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Departments */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-5">Departments</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {departments.map((dept) => (
                <div key={dept.name} className="rounded-xl bg-gray-50 p-4 hover:bg-gray-100 transition-colors">
                  <p className="text-sm font-bold text-gray-900">{dept.name}</p>
                  <p className="text-2xl font-extrabold text-gray-900 mt-1">{dept.count}</p>
                  <p className="text-xs text-gray-400 mt-1">Head: {dept.head}</p>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {activeView === "attendance" && (
        <div className="space-y-6">
          {/* Shift Overview */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-2">Today&apos;s Attendance</h2>
            <p className="text-sm text-gray-500 mb-5">Monday, 3 March 2026</p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {attendanceSummary.map((shift) => (
                <div key={shift.shift} className="rounded-xl bg-gray-50 p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <div className={cn("w-2.5 h-2.5 rounded-full", shift.color)} />
                    <span className="text-sm font-bold text-gray-900">{shift.shift}</span>
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <p className="text-xs text-gray-400">Scheduled</p>
                      <p className="text-lg font-extrabold text-gray-900">{shift.scheduled}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-400">Present</p>
                      <p className="text-lg font-extrabold text-emerald-600">{shift.present}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-400">Absent</p>
                      <p className="text-lg font-extrabold text-red-600">{shift.absent}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Attendance Summary Card */}
          <div className="bg-gradient-to-br from-gray-900 to-black rounded-2xl p-6 text-white">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div>
                <h2 className="text-lg font-bold">Attendance Summary</h2>
                <p className="text-gray-400 text-sm mt-1">Month of March 2026</p>
              </div>
              <div className="flex items-center gap-6">
                <div>
                  <p className="text-gray-400 text-xs font-medium uppercase tracking-wider">Avg Attendance</p>
                  <p className="text-xl font-extrabold">94.2%</p>
                </div>
                <div>
                  <p className="text-gray-400 text-xs font-medium uppercase tracking-wider">Total Shifts</p>
                  <p className="text-xl font-extrabold">156</p>
                </div>
                <div>
                  <p className="text-gray-400 text-xs font-medium uppercase tracking-wider">Absences</p>
                  <p className="text-xl font-extrabold text-amber-400">9</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeView === "leave" && (
        <div className="space-y-6">
          {/* Leave Requests */}
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <h2 className="text-lg font-bold text-gray-900">Leave Requests</h2>
              <div className="flex items-center gap-2">
                <span className="px-3 py-1.5 rounded-full bg-emerald-50 text-emerald-700 text-xs font-semibold">2 Approved</span>
                <span className="px-3 py-1.5 rounded-full bg-amber-50 text-amber-700 text-xs font-semibold">2 Pending</span>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50">
                    <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Employee</th>
                    <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Type</th>
                    <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">From</th>
                    <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">To</th>
                    <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Days</th>
                    <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Approver</th>
                    <th className="text-center px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {leaveRequests.map((req, i) => (
                    <tr key={i} className="hover:bg-gray-50/50 transition-colors">
                      <td className="px-6 py-3">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-black text-white flex items-center justify-center text-xs font-bold flex-shrink-0">
                            {req.employee.split(" ").map((n) => n[0]).join("")}
                          </div>
                          <span className="font-semibold text-gray-900">{req.employee}</span>
                        </div>
                      </td>
                      <td className="px-6 py-3">
                        <span className={cn(
                          "px-2 py-1 rounded-md text-xs font-medium",
                          req.type === "Annual Leave" ? "bg-blue-50 text-blue-700" :
                          req.type === "Sick Leave" ? "bg-red-50 text-red-700" : "bg-violet-50 text-violet-700"
                        )}>{req.type}</span>
                      </td>
                      <td className="px-6 py-3 text-gray-600">{req.from}</td>
                      <td className="px-6 py-3 text-gray-600">{req.to}</td>
                      <td className="px-6 py-3 text-right font-bold text-gray-900">{req.days}</td>
                      <td className="px-6 py-3 text-gray-500">{req.approver}</td>
                      <td className="px-6 py-3 text-center">
                        <span className={cn(
                          "px-2.5 py-1 rounded-full text-xs font-semibold",
                          req.status === "Approved" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
                        )}>{req.status}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Leave Balance Summary */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="rounded-2xl bg-blue-50 p-5">
              <p className="text-sm font-semibold text-blue-700 mb-2">Annual Leave</p>
              <p className="text-3xl font-extrabold text-gray-900">18 days</p>
              <p className="text-sm text-gray-500 mt-1">Average remaining per employee</p>
            </div>
            <div className="rounded-2xl bg-red-50 p-5">
              <p className="text-sm font-semibold text-red-700 mb-2">Sick Leave</p>
              <p className="text-3xl font-extrabold text-gray-900">8 days</p>
              <p className="text-sm text-gray-500 mt-1">Average remaining per employee</p>
            </div>
            <div className="rounded-2xl bg-violet-50 p-5">
              <p className="text-sm font-semibold text-violet-700 mb-2">Special Leave</p>
              <p className="text-3xl font-extrabold text-gray-900">5 days</p>
              <p className="text-sm text-gray-500 mt-1">Maternity, paternity, compassionate</p>
            </div>
          </div>
        </div>
      )}

      {/* Payroll Summary */}
      <div className="bg-gradient-to-br from-gray-900 to-black rounded-2xl p-6 text-white">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold">February 2026 Payroll</h2>
            <p className="text-gray-400 text-sm mt-1">Next payment: 28 Mar 2026</p>
          </div>
          <div className="flex items-center gap-6">
            <div>
              <p className="text-gray-400 text-xs font-medium uppercase tracking-wider">Gross Pay</p>
              <p className="text-xl font-extrabold">UGX 48.6M</p>
            </div>
            <div>
              <p className="text-gray-400 text-xs font-medium uppercase tracking-wider">Deductions</p>
              <p className="text-xl font-extrabold">UGX 9.7M</p>
            </div>
            <div>
              <p className="text-gray-400 text-xs font-medium uppercase tracking-wider">Net Pay</p>
              <p className="text-xl font-extrabold text-emerald-400">UGX 38.9M</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
