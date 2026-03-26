"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

// ── Mock data ───────────────────────────────────────────────────────────────

const financeKPIs = [
  { label: "Total Revenue", value: "UGX 484.2M", sub: "February 2026", change: "+18.2%", color: "emerald" },
  { label: "Total Expenses", value: "UGX 411.9M", sub: "February 2026", change: "+12.4%", color: "red" },
  { label: "Net Profit", value: "UGX 72.3M", sub: "14.9% margin", change: "+24.1%", color: "blue" },
  { label: "Outstanding", value: "UGX 8.4M", sub: "Receivables", change: "-5.2%", color: "amber" },
];

const chartOfAccounts = [
  { code: "1000", name: "Cash & Bank", type: "Asset", balance: "UGX 42.8M", children: 4 },
  { code: "1100", name: "Accounts Receivable", type: "Asset", balance: "UGX 8.4M", children: 2 },
  { code: "1200", name: "Inventory", type: "Asset", balance: "UGX 186M", children: 6 },
  { code: "2000", name: "Accounts Payable", type: "Liability", balance: "UGX 14.2M", children: 3 },
  { code: "2100", name: "Tax Payable", type: "Liability", balance: "UGX 6.8M", children: 2 },
  { code: "3000", name: "Owner's Equity", type: "Equity", balance: "UGX 350M", children: 1 },
  { code: "4000", name: "Sales Revenue", type: "Revenue", balance: "UGX 484.2M", children: 4 },
  { code: "5000", name: "Cost of Goods Sold", type: "Expense", balance: "UGX 342M", children: 3 },
  { code: "6000", name: "Operating Expenses", type: "Expense", balance: "UGX 69.9M", children: 8 },
];

const journalEntries = [
  { id: "JE-1042", date: "3 Mar 2026", description: "Daily fuel sales revenue", debit: "UGX 25.7M", credit: "—", account: "Sales", status: "Posted" },
  { id: "JE-1041", date: "3 Mar 2026", description: "Retail shop daily sales", debit: "UGX 3.8M", credit: "—", account: "Sales", status: "Posted" },
  { id: "JE-1040", date: "2 Mar 2026", description: "Fuel purchase — PMS 10,000L", debit: "—", credit: "UGX 38M", account: "Inventory", status: "Posted" },
  { id: "JE-1039", date: "1 Mar 2026", description: "Electricity bill — Main Branch", debit: "—", credit: "UGX 890K", account: "Utilities", status: "Posted" },
  { id: "JE-1038", date: "28 Feb 2026", description: "Staff salary — February", debit: "—", credit: "UGX 48.6M", account: "Payroll", status: "Posted" },
  { id: "JE-1037", date: "28 Feb 2026", description: "NSSF contributions — February", debit: "—", credit: "UGX 4.8M", account: "Payroll", status: "Posted" },
  { id: "JE-1036", date: "27 Feb 2026", description: "Rent payment — All branches", debit: "—", credit: "UGX 6.5M", account: "Rent", status: "Posted" },
  { id: "JE-1035", date: "26 Feb 2026", description: "Mobile money float top-up", debit: "UGX 5M", credit: "—", account: "Cash", status: "Posted" },
];

const budgetItems = [
  { category: "Fuel Purchases", budget: "UGX 380M", actual: "UGX 342M", variance: "UGX 38M", pct: 90 },
  { category: "Payroll", budget: "UGX 52M", actual: "UGX 48.6M", variance: "UGX 3.4M", pct: 93 },
  { category: "Utilities", budget: "UGX 15M", actual: "UGX 12.4M", variance: "UGX 2.6M", pct: 83 },
  { category: "Rent", budget: "UGX 7M", actual: "UGX 6.5M", variance: "UGX 500K", pct: 93 },
  { category: "Other Expenses", budget: "UGX 12M", actual: "UGX 8.9M", variance: "UGX 3.1M", pct: 74 },
];

const taxSummary = [
  { tax: "VAT (18%)", collected: "UGX 14.8M", remitted: "UGX 8.2M", outstanding: "UGX 6.6M", dueDate: "15 Mar 2026" },
  { tax: "PAYE", collected: "UGX 4.2M", remitted: "UGX 4.2M", outstanding: "UGX 0", dueDate: "15 Mar 2026" },
  { tax: "NSSF", collected: "UGX 4.8M", remitted: "UGX 0", outstanding: "UGX 4.8M", dueDate: "15 Mar 2026" },
];

const colorMap: Record<string, { bg: string; text: string; light: string }> = {
  emerald: { bg: "bg-emerald-500", text: "text-emerald-600", light: "bg-emerald-50" },
  blue: { bg: "bg-blue-500", text: "text-blue-600", light: "bg-blue-50" },
  red: { bg: "bg-red-500", text: "text-red-600", light: "bg-red-50" },
  amber: { bg: "bg-amber-500", text: "text-amber-600", light: "bg-amber-50" },
};

const typeColor: Record<string, { bg: string; text: string }> = {
  Asset: { bg: "bg-blue-50", text: "text-blue-700" },
  Liability: { bg: "bg-red-50", text: "text-red-700" },
  Equity: { bg: "bg-violet-50", text: "text-violet-700" },
  Revenue: { bg: "bg-emerald-50", text: "text-emerald-700" },
  Expense: { bg: "bg-amber-50", text: "text-amber-700" },
};

// ── Component ───────────────────────────────────────────────────────────────

export default function AccountingPage() {
  const [activeView, setActiveView] = useState<"overview" | "ledger" | "budget" | "tax">("overview");

  return (
    <div className="space-y-6 max-w-[1400px]">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight">
            Accounting
          </h1>
          <p className="text-sm text-gray-500 mt-1">General ledger, journal entries, budgets, and tax compliance</p>
        </div>
        <button className="px-4 py-2.5 rounded-xl bg-black text-white text-sm font-semibold hover:bg-zinc-800 transition-all shadow-sm">
          + New Entry
        </button>
      </div>

      {/* View Tabs */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-xl overflow-x-auto">
        {([
          { id: "overview", label: "Overview" },
          { id: "ledger", label: "Chart of Accounts" },
          { id: "budget", label: "Budgets" },
          { id: "tax", label: "Tax & Compliance" },
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

      {activeView === "overview" && <OverviewView />}
      {activeView === "ledger" && <LedgerView />}
      {activeView === "budget" && <BudgetView />}
      {activeView === "tax" && <TaxView />}
    </div>
  );
}

function OverviewView() {
  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {financeKPIs.map((stat) => {
          const c = colorMap[stat.color];
          return (
            <div key={stat.label} className="bg-white rounded-2xl p-5 border border-gray-100 shadow-sm hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-gray-500">{stat.label}</span>
                <span className={cn("text-xs font-bold px-2 py-0.5 rounded-full", c.light, c.text)}>{stat.change}</span>
              </div>
              <p className="text-2xl font-extrabold text-gray-900">{stat.value}</p>
              <p className="text-xs text-gray-400 mt-1">{stat.sub}</p>
            </div>
          );
        })}
      </div>

      {/* P&L Summary */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-2">Profit & Loss — February 2026</h2>
        <p className="text-sm text-gray-500 mb-6">Automated from journal entries</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
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
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-lg font-bold text-gray-900">Recent Journal Entries</h2>
          <span className="text-xs text-gray-400">{journalEntries.length} entries</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50">
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">ID</th>
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Date</th>
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Description</th>
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Account</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Debit</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Credit</th>
                <th className="text-center px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {journalEntries.map((entry) => (
                <tr key={entry.id} className="hover:bg-gray-50/50 transition-colors">
                  <td className="px-6 py-3 font-medium text-gray-900">{entry.id}</td>
                  <td className="px-6 py-3 text-gray-500 whitespace-nowrap">{entry.date}</td>
                  <td className="px-6 py-3 text-gray-900">{entry.description}</td>
                  <td className="px-6 py-3">
                    <span className="px-2 py-1 rounded-md bg-gray-100 text-gray-700 text-xs font-medium">{entry.account}</span>
                  </td>
                  <td className="px-6 py-3 text-right font-semibold text-gray-900">{entry.debit}</td>
                  <td className="px-6 py-3 text-right font-semibold text-gray-900">{entry.credit}</td>
                  <td className="px-6 py-3 text-center">
                    <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700">{entry.status}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function LedgerView() {
  return (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-900">Chart of Accounts</h2>
          <p className="text-sm text-gray-500 mt-1">All general ledger accounts</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50">
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Code</th>
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Account Name</th>
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Type</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Sub-accounts</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Balance</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {chartOfAccounts.map((account) => {
                const tc = typeColor[account.type];
                return (
                  <tr key={account.code} className="hover:bg-gray-50/50 transition-colors">
                    <td className="px-6 py-3">
                      <span className="px-2 py-1 rounded-md bg-gray-100 text-gray-700 text-xs font-mono font-bold">{account.code}</span>
                    </td>
                    <td className="px-6 py-3 font-semibold text-gray-900">{account.name}</td>
                    <td className="px-6 py-3">
                      <span className={cn("px-2.5 py-1 rounded-full text-xs font-semibold", tc.bg, tc.text)}>{account.type}</span>
                    </td>
                    <td className="px-6 py-3 text-right text-gray-500">{account.children}</td>
                    <td className="px-6 py-3 text-right font-bold text-gray-900">{account.balance}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function BudgetView() {
  return (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-lg font-bold text-gray-900">Budget vs Actual — February 2026</h2>
            <p className="text-sm text-gray-500 mt-1">Monthly budget tracking</p>
          </div>
          <div className="flex items-center gap-4 text-xs font-medium">
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-sm bg-gray-200" /> Budget
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-sm bg-black" /> Actual
            </span>
          </div>
        </div>
        <div className="space-y-5">
          {budgetItems.map((item) => (
            <div key={item.category}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-semibold text-gray-700">{item.category}</span>
                <div className="flex items-center gap-4 text-sm">
                  <span className="text-gray-500">{item.budget}</span>
                  <span className="font-bold text-gray-900">{item.actual}</span>
                  <span className={cn("font-bold", item.pct > 95 ? "text-red-600" : item.pct > 85 ? "text-amber-600" : "text-emerald-600")}>
                    {item.pct}%
                  </span>
                </div>
              </div>
              <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={cn(
                    "h-full rounded-full transition-all",
                    item.pct > 95 ? "bg-red-500" : item.pct > 85 ? "bg-amber-500" : "bg-emerald-500"
                  )}
                  style={{ width: `${item.pct}%` }}
                />
              </div>
              <p className="text-xs text-gray-400 mt-1">Remaining: {item.variance}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Budget Summary Card */}
      <div className="bg-gradient-to-br from-gray-900 to-black rounded-2xl p-6 text-white">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold">February 2026 Budget Summary</h2>
            <p className="text-gray-400 text-sm mt-1">Overall utilization: 87%</p>
          </div>
          <div className="flex items-center gap-6">
            <div>
              <p className="text-gray-400 text-xs font-medium uppercase tracking-wider">Total Budget</p>
              <p className="text-xl font-extrabold">UGX 466M</p>
            </div>
            <div>
              <p className="text-gray-400 text-xs font-medium uppercase tracking-wider">Actual</p>
              <p className="text-xl font-extrabold">UGX 411.9M</p>
            </div>
            <div>
              <p className="text-gray-400 text-xs font-medium uppercase tracking-wider">Savings</p>
              <p className="text-xl font-extrabold text-emerald-400">UGX 54.1M</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function TaxView() {
  return (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-900">Tax Obligations — March 2026</h2>
          <p className="text-sm text-gray-500 mt-1">Upcoming tax payments and compliance status</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50">
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Tax Type</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Collected</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Remitted</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Outstanding</th>
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Due Date</th>
                <th className="text-center px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {taxSummary.map((tax) => (
                <tr key={tax.tax} className="hover:bg-gray-50/50 transition-colors">
                  <td className="px-6 py-4 font-semibold text-gray-900">{tax.tax}</td>
                  <td className="px-6 py-4 text-right text-gray-600">{tax.collected}</td>
                  <td className="px-6 py-4 text-right text-gray-600">{tax.remitted}</td>
                  <td className={cn("px-6 py-4 text-right font-bold", tax.outstanding === "UGX 0" ? "text-emerald-600" : "text-amber-600")}>
                    {tax.outstanding}
                  </td>
                  <td className="px-6 py-4 text-gray-500">{tax.dueDate}</td>
                  <td className="px-6 py-4 text-center">
                    <span className={cn(
                      "px-2.5 py-1 rounded-full text-xs font-semibold",
                      tax.outstanding === "UGX 0" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
                    )}>
                      {tax.outstanding === "UGX 0" ? "Paid" : "Pending"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Tax Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="rounded-2xl bg-emerald-50 p-5">
          <p className="text-sm font-semibold text-emerald-700 mb-2">Total Collected</p>
          <p className="text-3xl font-extrabold text-gray-900">UGX 23.8M</p>
          <p className="text-sm text-gray-500 mt-1">VAT + PAYE + NSSF</p>
        </div>
        <div className="rounded-2xl bg-blue-50 p-5">
          <p className="text-sm font-semibold text-blue-700 mb-2">Total Remitted</p>
          <p className="text-3xl font-extrabold text-gray-900">UGX 12.4M</p>
          <p className="text-sm text-gray-500 mt-1">Paid to URA & NSSF</p>
        </div>
        <div className="rounded-2xl bg-amber-50 p-5">
          <p className="text-sm font-semibold text-amber-700 mb-2">Outstanding</p>
          <p className="text-3xl font-extrabold text-gray-900">UGX 11.4M</p>
          <p className="text-sm text-gray-500 mt-1">Due by 15 March 2026</p>
        </div>
      </div>
    </div>
  );
}
