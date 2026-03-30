"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import {
  useDashboard,
  useSalesSummary,
  useSalesByOutlet,
  useSalesByProduct,
  useSalesByPaymentMethod,
  useStockLevels,
  useStockMovement,
  useShiftSummary,
} from "@/lib/hooks/useReports";

// ── Report category definitions (static metadata) ──────────────────────────

const reportCategories = [
  {
    id: "sales",
    name: "Sales & Revenue",
    description: "Daily, weekly, monthly sales performance",
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    color: "emerald",
  },
  {
    id: "inventory",
    name: "Inventory & Stock",
    description: "Stock levels, movement, and valuation",
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
      </svg>
    ),
    color: "violet",
  },
  {
    id: "payments",
    name: "Payment Methods",
    description: "Cash, mobile money, bank, card breakdown",
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
      </svg>
    ),
    color: "blue",
  },
  {
    id: "shifts",
    name: "Shift Reports",
    description: "Shift reconciliation and cashier performance",
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    color: "amber",
  },
  {
    id: "outlets",
    name: "Outlet Performance",
    description: "Revenue and sales by outlet / branch",
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
      </svg>
    ),
    color: "rose",
  },
  {
    id: "products",
    name: "Top Products",
    description: "Best-selling products by revenue and quantity",
    icon: (
      <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z" />
      </svg>
    ),
    color: "gray",
  },
];

const colorMap: Record<string, { bg: string; text: string; light: string; border: string }> = {
  emerald: { bg: "bg-emerald-500", text: "text-emerald-600", light: "bg-emerald-50", border: "border-emerald-200" },
  blue: { bg: "bg-blue-500", text: "text-blue-600", light: "bg-blue-50", border: "border-blue-200" },
  violet: { bg: "bg-violet-500", text: "text-violet-600", light: "bg-violet-50", border: "border-violet-200" },
  amber: { bg: "bg-amber-500", text: "text-amber-600", light: "bg-amber-50", border: "border-amber-200" },
  rose: { bg: "bg-rose-500", text: "text-rose-600", light: "bg-rose-50", border: "border-rose-200" },
  gray: { bg: "bg-gray-500", text: "text-gray-600", light: "bg-gray-50", border: "border-gray-200" },
};

function formatCurrency(value: string | number | null | undefined) {
  if (value == null) return "UGX 0";
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "UGX 0";
  return `UGX ${num.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString("en-UG", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

// ── Component ───────────────────────────────────────────────────────────────

export default function ReportsPage() {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const dateParams = {
    ...(dateFrom && { date_from: dateFrom }),
    ...(dateTo && { date_to: dateTo }),
  };

  const { data: dashboard, isLoading: dashboardLoading } = useDashboard();
  const { data: salesSummary } = useSalesSummary(dateParams);
  const { data: salesByOutlet } = useSalesByOutlet(dateParams);
  const { data: salesByProduct } = useSalesByProduct(dateParams);
  const { data: salesByPayment } = useSalesByPaymentMethod(dateParams);
  const { data: stockLevels } = useStockLevels();
  const { data: stockMovement } = useStockMovement(dateParams);
  const { data: shiftSummary } = useShiftSummary(dateParams);

  const quickStats = [
    { label: "Today's Sales", value: String(dashboard?.today_sales ?? 0), sub: dashboard?.date ?? "Today" },
    { label: "Today's Revenue", value: formatCurrency(dashboard?.today_revenue), sub: "Completed sales" },
    { label: "Active Shifts", value: String(dashboard?.active_shifts ?? 0), sub: "Currently open" },
    { label: "Low Stock Items", value: String(dashboard?.low_stock_count ?? 0), sub: "Below reorder level" },
  ];

  return (
    <div className="space-y-6 max-w-[1400px]">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight">
            Reports
          </h1>
          <p className="text-sm text-gray-500 mt-1">Real-time analytics and business insights</p>
        </div>
        <div className="flex items-center gap-3">
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="px-3 py-2 rounded-xl border border-gray-200 bg-white text-sm text-gray-700 shadow-sm"
            placeholder="From"
          />
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="px-3 py-2 rounded-xl border border-gray-200 bg-white text-sm text-gray-700 shadow-sm"
            placeholder="To"
          />
        </div>
      </div>

      {/* Quick Stats (live from dashboard API) */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {quickStats.map((stat) => (
          <div key={stat.label} className="bg-white rounded-2xl p-5 border border-gray-100 shadow-sm">
            <p className="text-sm font-medium text-gray-500">{stat.label}</p>
            <p className="text-2xl font-extrabold text-gray-900 mt-1">
              {dashboardLoading ? "..." : stat.value}
            </p>
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
            const isSelected = selectedCategory === cat.id;
            return (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(isSelected ? null : cat.id)}
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
                  </div>
                </div>
                <p className="text-xs text-gray-500">{cat.description}</p>
              </button>
            );
          })}
        </div>
      </div>

      {/* Dynamic Report Data */}
      {(!selectedCategory || selectedCategory === "sales") && salesSummary && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <h2 className="text-lg font-bold text-gray-900 mb-4">Sales Summary</h2>
          <p className="text-xs text-gray-400 mb-4">{salesSummary.date_from} to {salesSummary.date_to}</p>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
            <div>
              <p className="text-xs text-gray-500">Total Sales</p>
              <p className="text-xl font-extrabold text-gray-900">{salesSummary.total_sales}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Revenue</p>
              <p className="text-xl font-extrabold text-gray-900">{formatCurrency(salesSummary.total_revenue)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Tax Collected</p>
              <p className="text-xl font-extrabold text-gray-900">{formatCurrency(salesSummary.total_tax)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Discounts</p>
              <p className="text-xl font-extrabold text-gray-900">{formatCurrency(salesSummary.total_discount)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Avg Sale</p>
              <p className="text-xl font-extrabold text-gray-900">{formatCurrency(salesSummary.avg_sale)}</p>
            </div>
          </div>
        </div>
      )}

      {(!selectedCategory || selectedCategory === "outlets") && salesByOutlet && salesByOutlet.length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="text-lg font-bold text-gray-900">Sales by Outlet</h2>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50">
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase">Outlet</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase">Sales</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase">Revenue</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {salesByOutlet.map((row) => (
                <tr key={row.outlet} className="hover:bg-gray-50/50">
                  <td className="px-6 py-3 font-semibold text-gray-900">{row.outlet_name}</td>
                  <td className="px-6 py-3 text-right text-gray-600">{row.total_sales}</td>
                  <td className="px-6 py-3 text-right font-bold text-gray-900">{formatCurrency(row.total_revenue)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(!selectedCategory || selectedCategory === "products") && salesByProduct && salesByProduct.length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="text-lg font-bold text-gray-900">Top Products</h2>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50">
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase">Product</th>
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase">SKU</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase">Qty Sold</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase">Revenue</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {salesByProduct.map((row) => (
                <tr key={row.product} className="hover:bg-gray-50/50">
                  <td className="px-6 py-3 font-semibold text-gray-900">{row.product_name}</td>
                  <td className="px-6 py-3"><span className="px-2 py-1 rounded-md bg-gray-100 text-gray-600 text-xs font-mono">{row.product_sku}</span></td>
                  <td className="px-6 py-3 text-right text-gray-600">{parseFloat(row.total_quantity).toLocaleString()}</td>
                  <td className="px-6 py-3 text-right font-bold text-gray-900">{formatCurrency(row.total_revenue)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(!selectedCategory || selectedCategory === "payments") && salesByPayment && salesByPayment.length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="text-lg font-bold text-gray-900">Payment Methods</h2>
          </div>
          <div className="p-6 grid grid-cols-2 sm:grid-cols-4 gap-4">
            {salesByPayment.map((pm) => (
              <div key={pm.payment_method} className="p-4 rounded-xl bg-gray-50">
                <p className="text-xs text-gray-500 capitalize">{pm.payment_method.replace("_", " ")}</p>
                <p className="text-xl font-extrabold text-gray-900 mt-1">{formatCurrency(pm.total_amount)}</p>
                <p className="text-xs text-gray-400 mt-1">{pm.count} transactions</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {(!selectedCategory || selectedCategory === "inventory") && stockMovement && stockMovement.length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="text-lg font-bold text-gray-900">Stock Movement Summary</h2>
          </div>
          <div className="p-6 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
            {stockMovement.map((sm) => (
              <div key={sm.movement_type} className="p-4 rounded-xl bg-gray-50">
                <p className="text-xs text-gray-500 capitalize">{sm.movement_type.replace("_", " ")}</p>
                <p className="text-xl font-extrabold text-gray-900 mt-1">{sm.count}</p>
                <p className={cn("text-xs mt-1 font-semibold",
                  parseFloat(sm.total_quantity) >= 0 ? "text-emerald-600" : "text-red-600"
                )}>
                  {parseFloat(sm.total_quantity) >= 0 ? "+" : ""}{parseFloat(sm.total_quantity).toLocaleString()} units
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {(!selectedCategory || selectedCategory === "shifts") && shiftSummary && shiftSummary.length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="text-lg font-bold text-gray-900">Shift Summary</h2>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50">
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase">Outlet</th>
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase">Opened</th>
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase">Closed</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase">Sales</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase">Revenue</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase">Opening</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase">Closing</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase">Variance</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {shiftSummary.map((shift) => {
                const closing = parseFloat(shift.closing_cash || "0");
                const expected = parseFloat(shift.expected_cash || "0");
                const variance = closing - expected;
                return (
                  <tr key={shift.id} className="hover:bg-gray-50/50">
                    <td className="px-6 py-3 font-semibold text-gray-900">{shift.outlet_name}</td>
                    <td className="px-6 py-3 text-gray-600 text-xs">{formatDate(shift.opened_at)}</td>
                    <td className="px-6 py-3 text-gray-600 text-xs">{formatDate(shift.closed_at)}</td>
                    <td className="px-6 py-3 text-right text-gray-600">{shift.total_sales}</td>
                    <td className="px-6 py-3 text-right font-bold text-gray-900">{formatCurrency(shift.total_revenue)}</td>
                    <td className="px-6 py-3 text-right text-gray-600">{formatCurrency(shift.opening_cash)}</td>
                    <td className="px-6 py-3 text-right text-gray-600">{formatCurrency(shift.closing_cash)}</td>
                    <td className={cn("px-6 py-3 text-right font-bold",
                      variance >= 0 ? "text-emerald-600" : "text-red-600"
                    )}>
                      {variance >= 0 ? "+" : ""}{formatCurrency(variance)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
