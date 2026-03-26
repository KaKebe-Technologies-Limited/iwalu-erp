"use client";

import { cn } from "@/lib/utils";

// ── Mock data ───────────────────────────────────────────────────────────────

const branchKPIs = [
  { label: "Total Branches", value: "3", sub: "2 operational, 1 head office", color: "emerald" },
  { label: "Total Staff", value: "52", sub: "Across all branches", color: "blue" },
  { label: "Combined Revenue", value: "UGX 484.2M", sub: "February 2026", color: "violet" },
  { label: "Active Pumps", value: "10", sub: "4 Main + 6 Lira", color: "amber" },
];

const branches = [
  {
    name: "Main Branch — Lira",
    type: "Fuel Station + Retail",
    address: "Plot 12, Olwol Road, Lira City",
    manager: "Sarah Nakamya",
    phone: "+256 700 100 001",
    staff: 28,
    pumps: 4,
    status: "Operational",
    revenue: "UGX 312M",
    expenses: "UGX 268M",
    profit: "UGX 44M",
    tanks: 2,
    shopArea: "120 sqm",
    operatingHours: "24/7",
    openedDate: "Jan 2024",
  },
  {
    name: "Lira Branch — Adyel",
    type: "Fuel Station + Retail",
    address: "Plot 5, Adyel Division, Lira City",
    manager: "Moses Kato (Acting)",
    phone: "+256 700 100 002",
    staff: 20,
    pumps: 6,
    status: "Operational",
    revenue: "UGX 172.2M",
    expenses: "UGX 143.9M",
    profit: "UGX 28.3M",
    tanks: 3,
    shopArea: "85 sqm",
    operatingHours: "6AM — 10PM",
    openedDate: "Jun 2024",
  },
  {
    name: "Head Office — Lira",
    type: "Administrative",
    address: "Plot 8, Station Road, Lira City",
    manager: "David Ssali",
    phone: "+256 700 100 003",
    staff: 4,
    pumps: 0,
    status: "Operational",
    revenue: "—",
    expenses: "UGX 8.2M",
    profit: "—",
    tanks: 0,
    shopArea: "—",
    operatingHours: "8AM — 5PM (Mon-Fri)",
    openedDate: "Jan 2024",
  },
];

const branchComparison = [
  { metric: "Monthly Revenue", main: "UGX 312M", lira: "UGX 172.2M", total: "UGX 484.2M" },
  { metric: "Monthly Expenses", main: "UGX 268M", lira: "UGX 143.9M", total: "UGX 411.9M" },
  { metric: "Net Profit", main: "UGX 44M", lira: "UGX 28.3M", total: "UGX 72.3M" },
  { metric: "Fuel Sold (Feb)", main: "142,000 L", lira: "98,000 L", total: "240,000 L" },
  { metric: "Retail Sales", main: "UGX 42M", lira: "UGX 26M", total: "UGX 68M" },
  { metric: "Staff Count", main: "28", lira: "20", total: "52*" },
  { metric: "Pumps", main: "4", lira: "6", total: "10" },
];

const colorMap: Record<string, { bg: string; text: string; light: string }> = {
  emerald: { bg: "bg-emerald-500", text: "text-emerald-600", light: "bg-emerald-50" },
  blue: { bg: "bg-blue-500", text: "text-blue-600", light: "bg-blue-50" },
  violet: { bg: "bg-violet-500", text: "text-violet-600", light: "bg-violet-50" },
  amber: { bg: "bg-amber-500", text: "text-amber-600", light: "bg-amber-50" },
};

// ── Component ───────────────────────────────────────────────────────────────

export default function BranchesPage() {
  return (
    <div className="space-y-6 max-w-[1400px]">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight">
            Branches
          </h1>
          <p className="text-sm text-gray-500 mt-1">Multi-branch management and performance comparison</p>
        </div>
        <button className="px-4 py-2.5 rounded-xl bg-black text-white text-sm font-semibold hover:bg-zinc-800 transition-all shadow-sm">
          + Add Branch
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {branchKPIs.map((stat) => {
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

      {/* Branch Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {branches.map((branch) => (
          <div key={branch.name} className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden hover:shadow-md transition-shadow">
            {/* Branch Header */}
            <div className="p-5 border-b border-gray-100">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-lg font-bold text-gray-900">{branch.name}</h3>
                <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700">
                  {branch.status}
                </span>
              </div>
              <p className="text-xs text-gray-500">{branch.type}</p>
              <p className="text-xs text-gray-400 mt-1">{branch.address}</p>
            </div>

            {/* Branch Details */}
            <div className="p-5 space-y-3">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-black text-white flex items-center justify-center text-xs font-bold flex-shrink-0">
                  {branch.manager.split(" ").map(n => n[0]).join("").slice(0, 2)}
                </div>
                <div>
                  <p className="text-sm font-semibold text-gray-900">{branch.manager}</p>
                  <p className="text-xs text-gray-400">{branch.phone}</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 mt-4">
                <div className="rounded-lg bg-gray-50 p-3">
                  <p className="text-xs text-gray-400">Staff</p>
                  <p className="text-lg font-extrabold text-gray-900">{branch.staff}</p>
                </div>
                <div className="rounded-lg bg-gray-50 p-3">
                  <p className="text-xs text-gray-400">Pumps</p>
                  <p className="text-lg font-extrabold text-gray-900">{branch.pumps}</p>
                </div>
                <div className="rounded-lg bg-gray-50 p-3">
                  <p className="text-xs text-gray-400">Tanks</p>
                  <p className="text-lg font-extrabold text-gray-900">{branch.tanks}</p>
                </div>
                <div className="rounded-lg bg-gray-50 p-3">
                  <p className="text-xs text-gray-400">Hours</p>
                  <p className="text-sm font-bold text-gray-900">{branch.operatingHours}</p>
                </div>
              </div>
            </div>

            {/* Branch Financials */}
            {branch.revenue !== "—" && (
              <div className="px-5 pb-5">
                <div className="rounded-xl bg-gray-50 p-4">
                  <p className="text-xs text-gray-400 font-medium uppercase tracking-wider mb-3">February 2026</p>
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600">Revenue</span>
                      <span className="font-bold text-gray-900">{branch.revenue}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600">Expenses</span>
                      <span className="font-bold text-gray-900">{branch.expenses}</span>
                    </div>
                    <div className="border-t border-gray-200 pt-2 flex justify-between text-sm font-bold">
                      <span>Profit</span>
                      <span className="text-emerald-600">{branch.profit}</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Branch Comparison Table */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-900">Branch Comparison — February 2026</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50">
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Metric</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Main Branch</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Lira Branch</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {branchComparison.map((row) => (
                <tr key={row.metric} className="hover:bg-gray-50/50 transition-colors">
                  <td className="px-6 py-3 font-semibold text-gray-900">{row.metric}</td>
                  <td className="px-6 py-3 text-right text-gray-600">{row.main}</td>
                  <td className="px-6 py-3 text-right text-gray-600">{row.lira}</td>
                  <td className="px-6 py-3 text-right font-bold text-gray-900">{row.total}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="px-6 py-3 bg-gray-50 border-t border-gray-100">
          <p className="text-xs text-gray-400">* Includes 4 Head Office staff</p>
        </div>
      </div>
    </div>
  );
}
