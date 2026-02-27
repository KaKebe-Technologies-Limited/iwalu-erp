"use client";

import { useState } from "react";
import { cn } from "../../lib/utils";
import { useAuthStore } from "@/lib/store/auth";

// ── Tab definitions ─────────────────────────────────────────────────────────

const tabs = [
  { id: "overview", label: "Overview" },
  { id: "fuel", label: "Fuel Station" },
  { id: "retail", label: "Retail POS" },
  { id: "finance", label: "Finance" },
  { id: "hr", label: "HR & Payroll" },
] as const;

type TabId = (typeof tabs)[number]["id"];

// ── Mock data ───────────────────────────────────────────────────────────────

const overviewStats = [
  { label: "Today's Revenue", value: "UGX 14.2M", change: "+12.3%", up: true, color: "emerald" },
  { label: "Fuel Sold (L)", value: "8,420", change: "+5.7%", up: true, color: "blue" },
  { label: "Retail Sales", value: "UGX 3.8M", change: "+8.1%", up: true, color: "violet" },
  { label: "Active Staff", value: "47 / 52", change: "90.4%", up: true, color: "amber" },
];

const fuelTanks = [
  { name: "Tank A — PMS (Petrol)", capacity: 50000, current: 32400, unit: "L", color: "bg-emerald-500" },
  { name: "Tank B — AGO (Diesel)", capacity: 45000, current: 12800, unit: "L", color: "bg-blue-500" },
  { name: "Tank C — Kerosene", capacity: 20000, current: 18200, unit: "L", color: "bg-amber-500" },
];

const pumpStatus = [
  { id: "P1", fuel: "PMS", status: "active", litres: 1247, revenue: "UGX 4.99M" },
  { id: "P2", fuel: "PMS", status: "active", litres: 983, revenue: "UGX 3.93M" },
  { id: "P3", fuel: "AGO", status: "idle", litres: 0, revenue: "UGX 0" },
  { id: "P4", fuel: "AGO", status: "active", litres: 2105, revenue: "UGX 7.58M" },
  { id: "P5", fuel: "PMS", status: "maintenance", litres: 0, revenue: "UGX 0" },
  { id: "P6", fuel: "Kerosene", status: "active", litres: 412, revenue: "UGX 1.24M" },
];

const recentTransactions = [
  { id: "TXN-1042", type: "Fuel Sale", amount: "UGX 180,000", time: "2 min ago", method: "Cash" },
  { id: "TXN-1041", type: "Shop Sale", amount: "UGX 45,500", time: "8 min ago", method: "Mobile Money" },
  { id: "TXN-1040", type: "Fuel Sale", amount: "UGX 320,000", time: "12 min ago", method: "Card" },
  { id: "TXN-1039", type: "Shop Sale", amount: "UGX 12,000", time: "18 min ago", method: "Cash" },
  { id: "TXN-1038", type: "Fuel Sale", amount: "UGX 95,000", time: "25 min ago", method: "Mobile Money" },
  { id: "TXN-1037", type: "Fuel Sale", amount: "UGX 540,000", time: "31 min ago", method: "Card" },
];

const topProducts = [
  { name: "PMS (Petrol)", sold: "4,230 L", revenue: "UGX 16.9M", trend: "+15%" },
  { name: "AGO (Diesel)", sold: "2,105 L", revenue: "UGX 7.6M", trend: "+8%" },
  { name: "Motor Oil 1L", sold: "84 units", revenue: "UGX 1.3M", trend: "+22%" },
  { name: "Bottled Water 500ml", sold: "312 units", revenue: "UGX 468K", trend: "+4%" },
  { name: "Kerosene", sold: "412 L", revenue: "UGX 1.2M", trend: "-3%" },
];

const financeSummary = [
  { label: "Total Revenue", value: "UGX 14.2M", sub: "Today" },
  { label: "Total Expenses", value: "UGX 8.7M", sub: "Today" },
  { label: "Net Profit", value: "UGX 5.5M", sub: "Today" },
  { label: "Outstanding", value: "UGX 2.1M", sub: "Receivables" },
];

const recentJournals = [
  { date: "27 Feb", description: "Fuel purchase — PMS 10,000L", debit: "UGX 38M", credit: "—", account: "Inventory" },
  { date: "27 Feb", description: "Daily fuel sales revenue", debit: "—", credit: "UGX 16.9M", account: "Sales" },
  { date: "26 Feb", description: "Staff salary — February", debit: "UGX 12.4M", credit: "—", account: "Payroll" },
  { date: "26 Feb", description: "Electricity bill — Main Branch", debit: "UGX 890K", credit: "—", account: "Utilities" },
  { date: "25 Feb", description: "Retail shop sales", debit: "—", credit: "UGX 3.2M", account: "Sales" },
];

const employees = [
  { name: "Sarah Nakamya", role: "Station Manager", branch: "Main Branch", status: "On Duty", shift: "Morning" },
  { name: "Peter Ouma", role: "Cashier", branch: "Main Branch", status: "On Duty", shift: "Morning" },
  { name: "Grace Achieng", role: "Pump Attendant", branch: "Lira Branch", status: "On Duty", shift: "Morning" },
  { name: "David Ssali", role: "Accountant", branch: "Head Office", status: "On Leave", shift: "—" },
  { name: "Janet Adong", role: "Pump Attendant", branch: "Main Branch", status: "Off Duty", shift: "Evening" },
  { name: "Moses Kato", role: "Store Keeper", branch: "Lira Branch", status: "On Duty", shift: "Morning" },
];

const hrStats = [
  { label: "Total Employees", value: "52" },
  { label: "On Duty Today", value: "47" },
  { label: "On Leave", value: "3" },
  { label: "Payroll (Feb)", value: "UGX 48.6M" },
];

// ── Revenue chart bars (mock weekly data) ───────────────────────────────────

const weeklyRevenue = [
  { day: "Mon", fuel: 12.1, retail: 2.8 },
  { day: "Tue", fuel: 10.4, retail: 3.2 },
  { day: "Wed", fuel: 14.8, retail: 2.5 },
  { day: "Thu", fuel: 11.2, retail: 4.1 },
  { day: "Fri", fuel: 16.3, retail: 3.7 },
  { day: "Sat", fuel: 18.9, retail: 5.2 },
  { day: "Sun", fuel: 9.6, retail: 2.1 },
];

const maxRevenue = Math.max(...weeklyRevenue.map((d) => d.fuel + d.retail));

// ── Helpers ─────────────────────────────────────────────────────────────────

const statusColor: Record<string, string> = {
  active: "bg-emerald-500",
  idle: "bg-gray-400",
  maintenance: "bg-red-500",
};

const statusLabel: Record<string, string> = {
  active: "Active",
  idle: "Idle",
  maintenance: "Maintenance",
};

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

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const user = useAuthStore((s) => s.user);
  const firstName = user?.firstName || "John";

  return (
    <div className="space-y-6 max-w-[1400px]">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500">
            {new Date().toLocaleDateString("en-UG", {
              weekday: "long",
              year: "numeric",
              month: "long",
              day: "numeric",
            })}
          </p>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight mt-1">
            Good {new Date().getHours() < 12 ? "morning" : new Date().getHours() < 17 ? "afternoon" : "evening"}, {firstName}
          </h1>
        </div>

        {/* Branch selector pill */}
        <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-full px-4 py-2 shadow-sm text-sm">
          <div className="w-2 h-2 rounded-full bg-emerald-500" />
          <span className="font-semibold text-gray-900">Main Branch — Lira</span>
          <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-xl overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "px-4 py-2.5 rounded-lg text-sm font-semibold whitespace-nowrap transition-all",
              activeTab === tab.id
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "overview" && <OverviewTab />}
      {activeTab === "fuel" && <FuelTab />}
      {activeTab === "retail" && <RetailTab />}
      {activeTab === "finance" && <FinanceTab />}
      {activeTab === "hr" && <HRTab />}
    </div>
  );
}

// ── OVERVIEW TAB ────────────────────────────────────────────────────────────

function OverviewTab() {
  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {overviewStats.map((stat) => {
          const c = colorMap[stat.color];
          return (
            <div
              key={stat.label}
              className="bg-white rounded-2xl p-5 border border-gray-100 shadow-sm hover:shadow-md transition-shadow"
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-gray-500">{stat.label}</span>
                <span className={cn("text-xs font-bold px-2 py-0.5 rounded-full", c.light, c.text)}>
                  {stat.change}
                </span>
              </div>
              <p className="text-2xl font-extrabold text-gray-900">{stat.value}</p>
              <div className={cn("mt-3 h-1 rounded-full", c.light)}>
                <div className={cn("h-1 rounded-full", c.bg)} style={{ width: "65%" }} />
              </div>
            </div>
          );
        })}
      </div>

      {/* Revenue Chart + Recent Transactions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Revenue Chart */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-lg font-bold text-gray-900">Weekly Revenue</h2>
              <p className="text-sm text-gray-500">Fuel vs Retail breakdown</p>
            </div>
            <div className="flex items-center gap-4 text-xs font-medium">
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-sm bg-black" /> Fuel
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-sm bg-blue-400" /> Retail
              </span>
            </div>
          </div>

          {/* Bar chart */}
          <div className="flex items-end gap-3 h-48">
            {weeklyRevenue.map((d) => {
              const fuelH = (d.fuel / maxRevenue) * 100;
              const retailH = (d.retail / maxRevenue) * 100;
              return (
                <div key={d.day} className="flex-1 flex flex-col items-center gap-1">
                  <div className="w-full flex flex-col items-center justify-end h-40">
                    <div
                      className="w-full max-w-[36px] bg-blue-400 rounded-t-md"
                      style={{ height: `${retailH}%` }}
                    />
                    <div
                      className="w-full max-w-[36px] bg-black rounded-t-md"
                      style={{ height: `${fuelH}%` }}
                    />
                  </div>
                  <span className="text-xs text-gray-500 font-medium">{d.day}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Recent Transactions */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <h2 className="text-lg font-bold text-gray-900">Live Transactions</h2>
          </div>
          <div className="divide-y divide-gray-50">
            {recentTransactions.map((tx) => (
              <div key={tx.id} className="px-5 py-3 flex items-center justify-between hover:bg-gray-50/50 transition-colors">
                <div>
                  <p className="text-sm font-semibold text-gray-900">{tx.type}</p>
                  <p className="text-xs text-gray-400">{tx.id} &middot; {tx.time}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-bold text-gray-900">{tx.amount}</p>
                  <p className="text-xs text-gray-400">{tx.method}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Tank Levels (compact) + Quick Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <h2 className="text-lg font-bold text-gray-900 mb-4">Tank Levels</h2>
          <div className="space-y-4">
            {fuelTanks.map((tank) => {
              const pct = Math.round((tank.current / tank.capacity) * 100);
              const isLow = pct < 30;
              return (
                <div key={tank.name}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-sm font-medium text-gray-700">{tank.name}</span>
                    <span className={cn("text-sm font-bold", isLow ? "text-red-600" : "text-gray-900")}>
                      {pct}%
                    </span>
                  </div>
                  <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className={cn("h-full rounded-full transition-all", isLow ? "bg-red-500" : tank.color)}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <p className="text-xs text-gray-400 mt-1">
                    {tank.current.toLocaleString()} / {tank.capacity.toLocaleString()} {tank.unit}
                  </p>
                </div>
              );
            })}
          </div>
        </div>

        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <h2 className="text-lg font-bold text-gray-900 mb-4">Top Selling Today</h2>
          <div className="space-y-3">
            {topProducts.slice(0, 4).map((product, i) => (
              <div
                key={product.name}
                className="flex items-center gap-4 p-3 rounded-xl bg-gray-50 hover:bg-gray-100 transition-colors"
              >
                <div className="w-8 h-8 rounded-lg bg-black text-white flex items-center justify-center text-sm font-bold flex-shrink-0">
                  {i + 1}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-gray-900 truncate">{product.name}</p>
                  <p className="text-xs text-gray-500">{product.sold}</p>
                </div>
                <div className="text-right flex-shrink-0">
                  <p className="text-sm font-bold text-gray-900">{product.revenue}</p>
                  <p className={cn(
                    "text-xs font-medium",
                    product.trend.startsWith("+") ? "text-emerald-600" : "text-red-600"
                  )}>
                    {product.trend}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── FUEL TAB ────────────────────────────────────────────────────────────────

function FuelTab() {
  return (
    <div className="space-y-6">
      {/* Fuel KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          { label: "Total Fuel Sold", value: "8,420 L", sub: "Across all pumps today" },
          { label: "Revenue", value: "UGX 25.7M", sub: "PMS + AGO + Kerosene" },
          { label: "Variance", value: "−12 L", sub: "0.14% — Within tolerance" },
        ].map((s) => (
          <div key={s.label} className="bg-white rounded-2xl p-5 border border-gray-100 shadow-sm">
            <p className="text-sm font-medium text-gray-500">{s.label}</p>
            <p className="text-2xl font-extrabold text-gray-900 mt-1">{s.value}</p>
            <p className="text-xs text-gray-400 mt-1">{s.sub}</p>
          </div>
        ))}
      </div>

      {/* Tank Levels - detailed */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-5">Tank Dip Readings</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {fuelTanks.map((tank) => {
            const pct = Math.round((tank.current / tank.capacity) * 100);
            const isLow = pct < 30;
            return (
              <div key={tank.name} className="relative rounded-2xl bg-gray-50 p-5 overflow-hidden">
                {/* Background fill effect */}
                <div
                  className={cn("absolute bottom-0 left-0 right-0 opacity-10", tank.color)}
                  style={{ height: `${pct}%` }}
                />
                <div className="relative">
                  <p className="text-sm font-semibold text-gray-700 mb-3">{tank.name}</p>
                  <p className={cn("text-4xl font-extrabold", isLow ? "text-red-600" : "text-gray-900")}>
                    {pct}%
                  </p>
                  <p className="text-sm text-gray-500 mt-1">
                    {tank.current.toLocaleString()} / {tank.capacity.toLocaleString()} {tank.unit}
                  </p>
                  {isLow && (
                    <div className="mt-3 flex items-center gap-2 text-red-600 text-xs font-semibold">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
                      </svg>
                      Low level — order required
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Pump Status Grid */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-5">Pump Status</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {pumpStatus.map((pump) => (
            <div
              key={pump.id}
              className={cn(
                "rounded-xl border p-4 transition-all",
                pump.status === "active"
                  ? "border-emerald-200 bg-emerald-50/50"
                  : pump.status === "maintenance"
                  ? "border-red-200 bg-red-50/50"
                  : "border-gray-200 bg-gray-50"
              )}
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-lg font-extrabold text-gray-900">{pump.id}</span>
                <span className="flex items-center gap-1.5 text-xs font-semibold">
                  <span className={cn("w-2 h-2 rounded-full", statusColor[pump.status])} />
                  {statusLabel[pump.status]}
                </span>
              </div>
              <p className="text-xs text-gray-500 font-medium mb-1">{pump.fuel}</p>
              {pump.status === "active" ? (
                <>
                  <p className="text-sm text-gray-700">
                    <span className="font-bold text-gray-900">{pump.litres.toLocaleString()} L</span> dispensed
                  </p>
                  <p className="text-sm font-semibold text-emerald-700 mt-1">{pump.revenue}</p>
                </>
              ) : (
                <p className="text-sm text-gray-400 italic">
                  {pump.status === "maintenance" ? "Under maintenance" : "No active session"}
                </p>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── RETAIL TAB ──────────────────────────────────────────────────────────────

function RetailTab() {
  return (
    <div className="space-y-6">
      {/* Retail KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        {[
          { label: "Shop Sales", value: "UGX 3.8M" },
          { label: "Transactions", value: "127" },
          { label: "Avg Basket", value: "UGX 29.9K" },
          { label: "Items Sold", value: "396" },
        ].map((s) => (
          <div key={s.label} className="bg-white rounded-2xl p-5 border border-gray-100 shadow-sm">
            <p className="text-sm font-medium text-gray-500">{s.label}</p>
            <p className="text-2xl font-extrabold text-gray-900 mt-1">{s.value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Products */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="text-lg font-bold text-gray-900">Top Products</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50">
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">#</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Product</th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Sold</th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Revenue</th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Trend</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {topProducts.map((p, i) => (
                  <tr key={p.name} className="hover:bg-gray-50/50 transition-colors">
                    <td className="px-6 py-3 font-bold text-gray-400">{i + 1}</td>
                    <td className="px-6 py-3 font-semibold text-gray-900">{p.name}</td>
                    <td className="px-6 py-3 text-right text-gray-600">{p.sold}</td>
                    <td className="px-6 py-3 text-right font-semibold text-gray-900">{p.revenue}</td>
                    <td className={cn(
                      "px-6 py-3 text-right font-bold",
                      p.trend.startsWith("+") ? "text-emerald-600" : "text-red-600"
                    )}>
                      {p.trend}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Recent Transactions */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="text-lg font-bold text-gray-900">Recent Sales</h2>
          </div>
          <div className="divide-y divide-gray-50">
            {recentTransactions.map((tx) => (
              <div key={tx.id} className="px-6 py-3.5 flex items-center justify-between hover:bg-gray-50/50 transition-colors">
                <div className="flex items-center gap-3">
                  <div className={cn(
                    "w-9 h-9 rounded-lg flex items-center justify-center text-xs font-bold flex-shrink-0",
                    tx.type === "Fuel Sale" ? "bg-emerald-50 text-emerald-700" : "bg-blue-50 text-blue-700"
                  )}>
                    {tx.type === "Fuel Sale" ? "F" : "S"}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-gray-900">{tx.amount}</p>
                    <p className="text-xs text-gray-400">{tx.id} &middot; {tx.method}</p>
                  </div>
                </div>
                <span className="text-xs text-gray-400">{tx.time}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Payment Methods Breakdown */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-5">Payment Methods</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[
            { method: "Cash", amount: "UGX 8.2M", pct: 58, color: "bg-black" },
            { method: "Mobile Money", amount: "UGX 4.1M", pct: 29, color: "bg-blue-500" },
            { method: "Card", amount: "UGX 1.9M", pct: 13, color: "bg-violet-500" },
          ].map((p) => (
            <div key={p.method} className="p-4 rounded-xl bg-gray-50">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-semibold text-gray-700">{p.method}</span>
                <span className="text-sm font-bold text-gray-900">{p.pct}%</span>
              </div>
              <p className="text-lg font-extrabold text-gray-900 mb-2">{p.amount}</p>
              <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                <div className={cn("h-full rounded-full", p.color)} style={{ width: `${p.pct}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── FINANCE TAB ─────────────────────────────────────────────────────────────

function FinanceTab() {
  return (
    <div className="space-y-6">
      {/* Finance KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {financeSummary.map((s) => (
          <div key={s.label} className="bg-white rounded-2xl p-5 border border-gray-100 shadow-sm">
            <p className="text-sm font-medium text-gray-500">{s.label}</p>
            <p className="text-2xl font-extrabold text-gray-900 mt-1">{s.value}</p>
            <p className="text-xs text-gray-400 mt-1">{s.sub}</p>
          </div>
        ))}
      </div>

      {/* P&L Summary */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-2">Profit & Loss — February 2026</h2>
        <p className="text-sm text-gray-500 mb-6">Automated from journal entries</p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Revenue */}
          <div className="rounded-2xl bg-emerald-50 p-5">
            <p className="text-sm font-semibold text-emerald-700 mb-3">Revenue</p>
            <div className="space-y-2">
              {[
                { item: "Fuel Sales", value: "UGX 412M" },
                { item: "Retail Sales", value: "UGX 68M" },
                { item: "Other Income", value: "UGX 4.2M" },
              ].map((r) => (
                <div key={r.item} className="flex justify-between text-sm">
                  <span className="text-gray-700">{r.item}</span>
                  <span className="font-semibold text-gray-900">{r.value}</span>
                </div>
              ))}
              <div className="border-t border-emerald-200 pt-2 mt-2 flex justify-between text-sm font-bold">
                <span>Total Revenue</span>
                <span className="text-emerald-700">UGX 484.2M</span>
              </div>
            </div>
          </div>

          {/* Expenses */}
          <div className="rounded-2xl bg-red-50 p-5">
            <p className="text-sm font-semibold text-red-700 mb-3">Expenses</p>
            <div className="space-y-2">
              {[
                { item: "Cost of Goods", value: "UGX 342M" },
                { item: "Payroll", value: "UGX 48.6M" },
                { item: "Utilities & Rent", value: "UGX 12.4M" },
                { item: "Other", value: "UGX 8.9M" },
              ].map((r) => (
                <div key={r.item} className="flex justify-between text-sm">
                  <span className="text-gray-700">{r.item}</span>
                  <span className="font-semibold text-gray-900">{r.value}</span>
                </div>
              ))}
              <div className="border-t border-red-200 pt-2 mt-2 flex justify-between text-sm font-bold">
                <span>Total Expenses</span>
                <span className="text-red-700">UGX 411.9M</span>
              </div>
            </div>
          </div>

          {/* Net */}
          <div className="rounded-2xl bg-black text-white p-5 flex flex-col justify-between">
            <p className="text-sm font-semibold text-gray-400 mb-3">Net Profit</p>
            <div>
              <p className="text-4xl font-extrabold">UGX 72.3M</p>
              <p className="text-sm text-gray-400 mt-2">14.9% margin</p>
            </div>
            <div className="mt-6 flex items-center gap-2 text-emerald-400 text-sm font-semibold">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
              </svg>
              +18.2% vs January
            </div>
          </div>
        </div>
      </div>

      {/* Journal Entries */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-900">Recent Journal Entries</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50">
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Date</th>
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Description</th>
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Account</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Debit</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Credit</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {recentJournals.map((j, i) => (
                <tr key={i} className="hover:bg-gray-50/50 transition-colors">
                  <td className="px-6 py-3 text-gray-500 whitespace-nowrap">{j.date}</td>
                  <td className="px-6 py-3 font-medium text-gray-900">{j.description}</td>
                  <td className="px-6 py-3">
                    <span className="px-2 py-1 rounded-md bg-gray-100 text-gray-700 text-xs font-medium">
                      {j.account}
                    </span>
                  </td>
                  <td className="px-6 py-3 text-right font-semibold text-gray-900">{j.debit}</td>
                  <td className="px-6 py-3 text-right font-semibold text-gray-900">{j.credit}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ── HR TAB ──────────────────────────────────────────────────────────────────

function HRTab() {
  return (
    <div className="space-y-6">
      {/* HR KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {hrStats.map((s) => (
          <div key={s.label} className="bg-white rounded-2xl p-5 border border-gray-100 shadow-sm">
            <p className="text-sm font-medium text-gray-500">{s.label}</p>
            <p className="text-2xl font-extrabold text-gray-900 mt-1">{s.value}</p>
          </div>
        ))}
      </div>

      {/* Shift Overview */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-2">Today's Shift Schedule</h2>
        <p className="text-sm text-gray-500 mb-5">Thursday, 27 February 2026</p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
          {[
            { shift: "Morning", time: "6:00 AM — 2:00 PM", staff: 18, color: "bg-amber-500" },
            { shift: "Afternoon", time: "2:00 PM — 10:00 PM", staff: 16, color: "bg-blue-500" },
            { shift: "Night", time: "10:00 PM — 6:00 AM", staff: 8, color: "bg-violet-500" },
          ].map((s) => (
            <div key={s.shift} className="rounded-xl bg-gray-50 p-4">
              <div className="flex items-center gap-2 mb-2">
                <div className={cn("w-2.5 h-2.5 rounded-full", s.color)} />
                <span className="text-sm font-bold text-gray-900">{s.shift} Shift</span>
              </div>
              <p className="text-xs text-gray-500 mb-2">{s.time}</p>
              <p className="text-lg font-extrabold text-gray-900">{s.staff} <span className="text-sm font-normal text-gray-500">staff</span></p>
            </div>
          ))}
        </div>
      </div>

      {/* Employee Table */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-lg font-bold text-gray-900">Employees</h2>
          <div className="flex items-center gap-2 bg-gray-100 rounded-lg px-3 py-2">
            <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              placeholder="Search employees..."
              className="bg-transparent text-sm outline-none placeholder-gray-400 w-40"
            />
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50">
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Employee</th>
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Role</th>
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Branch</th>
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Shift</th>
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {employees.map((emp) => {
                const dc = dutyColor[emp.status] || { bg: "bg-gray-100", text: "text-gray-600" };
                return (
                  <tr key={emp.name} className="hover:bg-gray-50/50 transition-colors">
                    <td className="px-6 py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-black text-white flex items-center justify-center text-xs font-bold flex-shrink-0">
                          {emp.name.split(" ").map((n) => n[0]).join("")}
                        </div>
                        <span className="font-semibold text-gray-900">{emp.name}</span>
                      </div>
                    </td>
                    <td className="px-6 py-3 text-gray-600">{emp.role}</td>
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

      {/* Payroll Summary */}
      <div className="bg-gradient-to-br from-gray-900 to-black rounded-2xl p-6 text-white">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold">February 2026 Payroll</h2>
            <p className="text-gray-400 text-sm mt-1">Next payment: 28 Feb 2026</p>
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
