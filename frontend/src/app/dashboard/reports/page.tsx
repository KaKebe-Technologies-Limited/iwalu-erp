"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

// ── Mock data ───────────────────────────────────────────────────────────────

const reportCategories = [
  {
    name: "Sales & Revenue",
    description: "Daily, weekly, monthly sales performance",
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    reports: 8,
    color: "emerald",
  },
  {
    name: "Fuel Operations",
    description: "Pump performance, tank levels, reconciliation",
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
      </svg>
    ),
    reports: 6,
    color: "blue",
  },
  {
    name: "Inventory & Stock",
    description: "Stock movement, aging, valuation reports",
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
      </svg>
    ),
    reports: 5,
    color: "violet",
  },
  {
    name: "Financial Statements",
    description: "P&L, balance sheet, cash flow",
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
      </svg>
    ),
    reports: 4,
    color: "amber",
  },
  {
    name: "HR & Payroll",
    description: "Attendance, leave, payroll summaries",
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
      </svg>
    ),
    reports: 5,
    color: "rose",
  },
  {
    name: "Audit & Activity",
    description: "User actions, system logs, audit trails",
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
      </svg>
    ),
    reports: 3,
    color: "gray",
  },
];

const recentReports = [
  { name: "Daily Sales Summary", category: "Sales & Revenue", generated: "Today, 6:00 AM", by: "System (Auto)", format: "PDF", size: "245 KB" },
  { name: "Fuel Reconciliation — 2 Mar", category: "Fuel Operations", generated: "2 Mar, 10:30 PM", by: "Sarah Nakamya", format: "PDF", size: "180 KB" },
  { name: "February P&L Statement", category: "Financial Statements", generated: "1 Mar, 12:00 AM", by: "System (Auto)", format: "Excel", size: "520 KB" },
  { name: "Monthly Payroll Report", category: "HR & Payroll", generated: "28 Feb, 4:00 PM", by: "David Ssali", format: "PDF", size: "340 KB" },
  { name: "Stock Valuation Report", category: "Inventory & Stock", generated: "28 Feb, 2:00 PM", by: "Moses Kato", format: "Excel", size: "890 KB" },
  { name: "Weekly Fuel Performance", category: "Fuel Operations", generated: "24 Feb, 11:00 PM", by: "System (Auto)", format: "PDF", size: "210 KB" },
];

const quickStats = [
  { label: "Reports Generated", value: "142", sub: "This month" },
  { label: "Auto-generated", value: "98", sub: "Daily & weekly" },
  { label: "Downloads", value: "67", sub: "This month" },
  { label: "Scheduled", value: "12", sub: "Active schedules" },
];

const colorMap: Record<string, { bg: string; text: string; light: string; border: string }> = {
  emerald: { bg: "bg-emerald-500", text: "text-emerald-600", light: "bg-emerald-50", border: "border-emerald-200" },
  blue: { bg: "bg-blue-500", text: "text-blue-600", light: "bg-blue-50", border: "border-blue-200" },
  violet: { bg: "bg-violet-500", text: "text-violet-600", light: "bg-violet-50", border: "border-violet-200" },
  amber: { bg: "bg-amber-500", text: "text-amber-600", light: "bg-amber-50", border: "border-amber-200" },
  rose: { bg: "bg-rose-500", text: "text-rose-600", light: "bg-rose-50", border: "border-rose-200" },
  gray: { bg: "bg-gray-500", text: "text-gray-600", light: "bg-gray-50", border: "border-gray-200" },
};

// ── Component ───────────────────────────────────────────────────────────────

export default function ReportsPage() {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  return (
    <div className="space-y-6 max-w-[1400px]">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight">
            Reports
          </h1>
          <p className="text-sm text-gray-500 mt-1">Generate, view, and export business reports</p>
        </div>
        <div className="flex items-center gap-3">
          <button className="px-4 py-2.5 rounded-xl border border-gray-200 bg-white text-sm font-semibold text-gray-700 hover:bg-gray-50 transition-all shadow-sm">
            Schedule Report
          </button>
          <button className="px-4 py-2.5 rounded-xl bg-black text-white text-sm font-semibold hover:bg-zinc-800 transition-all shadow-sm">
            + Generate Report
          </button>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {quickStats.map((stat) => (
          <div key={stat.label} className="bg-white rounded-2xl p-5 border border-gray-100 shadow-sm">
            <p className="text-sm font-medium text-gray-500">{stat.label}</p>
            <p className="text-2xl font-extrabold text-gray-900 mt-1">{stat.value}</p>
            <p className="text-xs text-gray-400 mt-1">{stat.sub}</p>
          </div>
        ))}
      </div>

      {/* Report Categories */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-5">Report Categories</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {reportCategories.map((cat) => {
            const c = colorMap[cat.color];
            const isSelected = selectedCategory === cat.name;
            return (
              <button
                key={cat.name}
                onClick={() => setSelectedCategory(isSelected ? null : cat.name)}
                className={cn(
                  "rounded-xl border p-5 text-left transition-all hover:shadow-md",
                  isSelected ? cn(c.light, c.border) : "border-gray-100 bg-white hover:bg-gray-50"
                )}
              >
                <div className="flex items-center gap-3 mb-3">
                  <div className={cn("w-10 h-10 rounded-xl flex items-center justify-center", c.light, c.text)}>
                    {cat.icon}
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-bold text-gray-900">{cat.name}</p>
                    <p className="text-xs text-gray-400">{cat.reports} reports</p>
                  </div>
                </div>
                <p className="text-xs text-gray-500">{cat.description}</p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Recent Reports */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-lg font-bold text-gray-900">
            {selectedCategory ? `${selectedCategory} Reports` : "Recent Reports"}
          </h2>
          {selectedCategory && (
            <button
              onClick={() => setSelectedCategory(null)}
              className="text-sm font-semibold text-gray-500 hover:text-gray-900 transition-colors"
            >
              Show All
            </button>
          )}
        </div>
        <div className="divide-y divide-gray-50">
          {recentReports
            .filter((r) => !selectedCategory || r.category === selectedCategory)
            .map((report) => (
              <div key={report.name + report.generated} className="px-6 py-4 flex items-center justify-between hover:bg-gray-50/50 transition-colors">
                <div className="flex items-center gap-4">
                  <div className={cn(
                    "w-10 h-10 rounded-xl flex items-center justify-center text-xs font-bold flex-shrink-0",
                    report.format === "PDF" ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700"
                  )}>
                    {report.format}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-gray-900">{report.name}</p>
                    <p className="text-xs text-gray-400">
                      {report.category} &middot; {report.by} &middot; {report.size}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-xs text-gray-400 whitespace-nowrap">{report.generated}</span>
                  <button className="p-2 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                  </button>
                </div>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}
