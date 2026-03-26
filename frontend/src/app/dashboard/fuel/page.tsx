"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

// ── Mock data ───────────────────────────────────────────────────────────────

const fuelKPIs = [
  { label: "Total Fuel Sold", value: "8,420 L", sub: "Today across all pumps", color: "emerald" },
  { label: "Fuel Revenue", value: "UGX 25.7M", sub: "PMS + AGO + Kerosene", color: "blue" },
  { label: "Variance", value: "−12 L", sub: "0.14% — Within tolerance", color: "violet" },
  { label: "Active Pumps", value: "4 / 6", sub: "1 idle, 1 maintenance", color: "amber" },
];

const tanks = [
  { name: "Tank A — PMS (Petrol)", capacity: 50000, current: 32400, unit: "L", color: "bg-emerald-500", lightColor: "bg-emerald-50", textColor: "text-emerald-700", lastDip: "Today 6:00 AM", deliveryDue: "3 Mar 2026" },
  { name: "Tank B — AGO (Diesel)", capacity: 45000, current: 12800, unit: "L", color: "bg-blue-500", lightColor: "bg-blue-50", textColor: "text-blue-700", lastDip: "Today 6:00 AM", deliveryDue: "1 Mar 2026" },
  { name: "Tank C — Kerosene", capacity: 20000, current: 18200, unit: "L", color: "bg-amber-500", lightColor: "bg-amber-50", textColor: "text-amber-700", lastDip: "Today 6:00 AM", deliveryDue: "8 Mar 2026" },
];

const pumps = [
  { id: "P1", fuel: "PMS", status: "active", attendant: "Grace Achieng", litres: 1247, revenue: "UGX 4.99M", shift: "Morning" },
  { id: "P2", fuel: "PMS", status: "active", attendant: "Peter Ouma", litres: 983, revenue: "UGX 3.93M", shift: "Morning" },
  { id: "P3", fuel: "AGO", status: "idle", attendant: "—", litres: 0, revenue: "UGX 0", shift: "—" },
  { id: "P4", fuel: "AGO", status: "active", attendant: "Moses Kato", litres: 2105, revenue: "UGX 7.58M", shift: "Morning" },
  { id: "P5", fuel: "PMS", status: "maintenance", attendant: "—", litres: 0, revenue: "UGX 0", shift: "—" },
  { id: "P6", fuel: "Kerosene", status: "active", attendant: "Janet Adong", litres: 412, revenue: "UGX 1.24M", shift: "Morning" },
];

const fuelSales = [
  { id: "FS-2041", pump: "P1", fuel: "PMS", litres: "45.0 L", amount: "UGX 180,000", attendant: "Grace Achieng", method: "Cash", time: "2 min ago" },
  { id: "FS-2040", pump: "P4", fuel: "AGO", litres: "80.0 L", amount: "UGX 320,000", attendant: "Moses Kato", method: "Card", time: "12 min ago" },
  { id: "FS-2039", pump: "P2", fuel: "PMS", litres: "23.8 L", amount: "UGX 95,000", attendant: "Peter Ouma", method: "Mobile Money", time: "25 min ago" },
  { id: "FS-2038", pump: "P4", fuel: "AGO", litres: "135.0 L", amount: "UGX 540,000", attendant: "Moses Kato", method: "Card", time: "31 min ago" },
  { id: "FS-2037", pump: "P6", fuel: "Kerosene", litres: "12.0 L", amount: "UGX 36,000", attendant: "Janet Adong", method: "Cash", time: "38 min ago" },
  { id: "FS-2036", pump: "P1", fuel: "PMS", litres: "60.0 L", amount: "UGX 240,000", attendant: "Grace Achieng", method: "Mobile Money", time: "45 min ago" },
];

const dailyReconciliation = [
  { fuel: "PMS (Petrol)", opening: "35,240 L", received: "0 L", sold: "4,230 L", closing: "31,010 L", expected: "31,010 L", variance: "0 L", status: "OK" },
  { fuel: "AGO (Diesel)", opening: "15,180 L", received: "0 L", sold: "2,105 L", closing: "12,800 L", expected: "13,075 L", variance: "−275 L", status: "Check" },
  { fuel: "Kerosene", opening: "18,612 L", received: "0 L", sold: "412 L", closing: "18,200 L", expected: "18,200 L", variance: "0 L", status: "OK" },
];

const colorMap: Record<string, { bg: string; text: string; light: string }> = {
  emerald: { bg: "bg-emerald-500", text: "text-emerald-600", light: "bg-emerald-50" },
  blue: { bg: "bg-blue-500", text: "text-blue-600", light: "bg-blue-50" },
  violet: { bg: "bg-violet-500", text: "text-violet-600", light: "bg-violet-50" },
  amber: { bg: "bg-amber-500", text: "text-amber-600", light: "bg-amber-50" },
};

const statusColor: Record<string, string> = { active: "bg-emerald-500", idle: "bg-gray-400", maintenance: "bg-red-500" };
const statusLabel: Record<string, string> = { active: "Active", idle: "Idle", maintenance: "Maintenance" };

// ── Component ───────────────────────────────────────────────────────────────

export default function FuelStationPage() {
  const [activeView, setActiveView] = useState<"overview" | "reconciliation">("overview");

  return (
    <div className="space-y-6 max-w-[1400px]">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight">
            Fuel Station
          </h1>
          <p className="text-sm text-gray-500 mt-1">Monitor pumps, tanks, and daily fuel operations</p>
        </div>
        <div className="flex items-center gap-3">
          <button className="px-4 py-2.5 rounded-xl border border-gray-200 bg-white text-sm font-semibold text-gray-700 hover:bg-gray-50 transition-all shadow-sm">
            Record Dip
          </button>
          <button className="px-4 py-2.5 rounded-xl bg-black text-white text-sm font-semibold hover:bg-zinc-800 transition-all shadow-sm">
            Add Delivery
          </button>
        </div>
      </div>

      {/* View Toggle */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-xl w-fit">
        {(["overview", "reconciliation"] as const).map((view) => (
          <button
            key={view}
            onClick={() => setActiveView(view)}
            className={cn(
              "px-4 py-2.5 rounded-lg text-sm font-semibold whitespace-nowrap transition-all capitalize",
              activeView === view
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            )}
          >
            {view === "overview" ? "Live Overview" : "Daily Reconciliation"}
          </button>
        ))}
      </div>

      {activeView === "overview" ? <OverviewView /> : <ReconciliationView />}
    </div>
  );
}

function OverviewView() {
  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {fuelKPIs.map((stat) => {
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

      {/* Tank Levels */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-5">Tank Dip Readings</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {tanks.map((tank) => {
            const pct = Math.round((tank.current / tank.capacity) * 100);
            const isLow = pct < 30;
            return (
              <div key={tank.name} className="relative rounded-2xl bg-gray-50 p-5 overflow-hidden">
                <div className={cn("absolute bottom-0 left-0 right-0 opacity-10", tank.color)} style={{ height: `${pct}%` }} />
                <div className="relative">
                  <p className="text-sm font-semibold text-gray-700 mb-3">{tank.name}</p>
                  <p className={cn("text-4xl font-extrabold", isLow ? "text-red-600" : "text-gray-900")}>{pct}%</p>
                  <p className="text-sm text-gray-500 mt-1">{tank.current.toLocaleString()} / {tank.capacity.toLocaleString()} {tank.unit}</p>
                  <div className="mt-3 flex items-center gap-4 text-xs text-gray-400">
                    <span>Last dip: {tank.lastDip}</span>
                    <span>Delivery: {tank.deliveryDue}</span>
                  </div>
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
          {pumps.map((pump) => (
            <div
              key={pump.id}
              className={cn(
                "rounded-xl border p-4 transition-all",
                pump.status === "active" ? "border-emerald-200 bg-emerald-50/50" :
                pump.status === "maintenance" ? "border-red-200 bg-red-50/50" : "border-gray-200 bg-gray-50"
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
                  <div className="mt-2 pt-2 border-t border-gray-200/50 flex items-center gap-2">
                    <div className="w-5 h-5 rounded-full bg-black text-white flex items-center justify-center text-[10px] font-bold">
                      {pump.attendant.split(" ").map(n => n[0]).join("")}
                    </div>
                    <span className="text-xs text-gray-500">{pump.attendant} &middot; {pump.shift}</span>
                  </div>
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

      {/* Recent Fuel Sales */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-lg font-bold text-gray-900">Recent Fuel Sales</h2>
          <span className="text-xs text-gray-400 font-medium">Live</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50">
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">ID</th>
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Pump</th>
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Fuel</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Litres</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Amount</th>
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Attendant</th>
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Payment</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {fuelSales.map((sale) => (
                <tr key={sale.id} className="hover:bg-gray-50/50 transition-colors">
                  <td className="px-6 py-3 font-medium text-gray-900">{sale.id}</td>
                  <td className="px-6 py-3">
                    <span className="px-2 py-1 rounded-md bg-gray-100 text-gray-700 text-xs font-medium">{sale.pump}</span>
                  </td>
                  <td className="px-6 py-3 text-gray-600">{sale.fuel}</td>
                  <td className="px-6 py-3 text-right font-semibold text-gray-900">{sale.litres}</td>
                  <td className="px-6 py-3 text-right font-bold text-gray-900">{sale.amount}</td>
                  <td className="px-6 py-3 text-gray-600">{sale.attendant}</td>
                  <td className="px-6 py-3">
                    <span className={cn(
                      "px-2.5 py-1 rounded-full text-xs font-semibold",
                      sale.method === "Cash" ? "bg-emerald-50 text-emerald-700" :
                      sale.method === "Mobile Money" ? "bg-blue-50 text-blue-700" : "bg-violet-50 text-violet-700"
                    )}>{sale.method}</span>
                  </td>
                  <td className="px-6 py-3 text-right text-gray-400 text-xs">{sale.time}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function ReconciliationView() {
  return (
    <div className="space-y-6">
      {/* Date & Shift Info */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-gray-900">Daily Fuel Reconciliation</h2>
            <p className="text-sm text-gray-500 mt-1">Monday, 3 March 2026 — Morning Shift</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="px-3 py-1.5 rounded-full bg-emerald-50 text-emerald-700 text-xs font-semibold">2 of 3 OK</span>
            <span className="px-3 py-1.5 rounded-full bg-amber-50 text-amber-700 text-xs font-semibold">1 Needs Review</span>
          </div>
        </div>
      </div>

      {/* Reconciliation Table */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50">
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Fuel Type</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Opening</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Received</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Sold</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Closing (Dip)</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Expected</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Variance</th>
                <th className="text-center px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {dailyReconciliation.map((row) => (
                <tr key={row.fuel} className="hover:bg-gray-50/50 transition-colors">
                  <td className="px-6 py-4 font-semibold text-gray-900">{row.fuel}</td>
                  <td className="px-6 py-4 text-right text-gray-600">{row.opening}</td>
                  <td className="px-6 py-4 text-right text-gray-600">{row.received}</td>
                  <td className="px-6 py-4 text-right font-semibold text-gray-900">{row.sold}</td>
                  <td className="px-6 py-4 text-right font-semibold text-gray-900">{row.closing}</td>
                  <td className="px-6 py-4 text-right text-gray-600">{row.expected}</td>
                  <td className={cn("px-6 py-4 text-right font-bold", row.variance.startsWith("−") ? "text-red-600" : "text-emerald-600")}>{row.variance}</td>
                  <td className="px-6 py-4 text-center">
                    <span className={cn(
                      "px-2.5 py-1 rounded-full text-xs font-semibold",
                      row.status === "OK" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
                    )}>{row.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Shift Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="rounded-2xl bg-emerald-50 p-5">
          <p className="text-sm font-semibold text-emerald-700 mb-3">Total Sold</p>
          <p className="text-3xl font-extrabold text-gray-900">6,747 L</p>
          <p className="text-sm text-gray-500 mt-1">Across 3 fuel types</p>
        </div>
        <div className="rounded-2xl bg-blue-50 p-5">
          <p className="text-sm font-semibold text-blue-700 mb-3">Total Revenue</p>
          <p className="text-3xl font-extrabold text-gray-900">UGX 25.7M</p>
          <p className="text-sm text-gray-500 mt-1">Cash: 58% &middot; MoMo: 29% &middot; Card: 13%</p>
        </div>
        <div className={cn(
          "rounded-2xl p-5",
          dailyReconciliation.some(r => r.status !== "OK") ? "bg-amber-50" : "bg-emerald-50"
        )}>
          <p className={cn(
            "text-sm font-semibold mb-3",
            dailyReconciliation.some(r => r.status !== "OK") ? "text-amber-700" : "text-emerald-700"
          )}>Net Variance</p>
          <p className="text-3xl font-extrabold text-gray-900">−275 L</p>
          <p className="text-sm text-gray-500 mt-1">AGO tank requires investigation</p>
        </div>
      </div>
    </div>
  );
}
