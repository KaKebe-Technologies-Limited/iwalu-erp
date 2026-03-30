"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { useProducts, useLowStockProducts } from "@/lib/hooks/useProducts";
import { useCategories } from "@/lib/hooks/useCategories";
import { useSuppliers } from "@/lib/hooks/useSuppliers";
import { useStockAuditLog } from "@/lib/hooks/useStockAuditLog";
import { useDashboard } from "@/lib/hooks/useReports";
import type { Product, StockAuditLog } from "@/lib/types";

const colorMap: Record<string, { bg: string; text: string; light: string }> = {
  emerald: { bg: "bg-emerald-500", text: "text-emerald-600", light: "bg-emerald-50" },
  blue: { bg: "bg-blue-500", text: "text-blue-600", light: "bg-blue-50" },
  violet: { bg: "bg-violet-500", text: "text-violet-600", light: "bg-violet-50" },
  red: { bg: "bg-red-500", text: "text-red-600", light: "bg-red-50" },
};

function movementBadge(type: StockAuditLog["movement_type"]) {
  switch (type) {
    case "purchase":
      return { label: "IN", cls: "bg-emerald-50 text-emerald-700" };
    case "sale":
      return { label: "S", cls: "bg-blue-50 text-blue-700" };
    case "transfer_out":
      return { label: "TF", cls: "bg-violet-50 text-violet-700" };
    case "transfer_in":
      return { label: "TF", cls: "bg-teal-50 text-teal-700" };
    case "void":
      return { label: "V", cls: "bg-orange-50 text-orange-700" };
    case "adjustment":
    default:
      return { label: "AD", cls: "bg-amber-50 text-amber-700" };
  }
}

function formatCurrency(value: string | number) {
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "UGX 0";
  if (num >= 1_000_000) return `UGX ${(num / 1_000_000).toFixed(1)}M`;
  if (num >= 1_000) return `UGX ${(num / 1_000).toFixed(0)}K`;
  return `UGX ${num.toLocaleString()}`;
}

export default function InventoryPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [filterStatus, setFilterStatus] = useState<"all" | "low">("all");

  const { data: productsData, isLoading: productsLoading } = useProducts({ search: searchQuery });
  const { data: lowStockData } = useLowStockProducts();
  const { data: categoriesData } = useCategories();
  const { data: suppliersData } = useSuppliers();
  const { data: auditData } = useStockAuditLog();
  const { data: dashboardData } = useDashboard();

  const allProducts = productsData?.results ?? [];
  const lowStockProducts = lowStockData?.results ?? [];
  const displayProducts = filterStatus === "low" ? lowStockProducts : allProducts;
  const categories = categoriesData?.results ?? [];
  const suppliers = suppliersData?.results ?? [];
  const auditLogs = auditData?.results ?? [];

  const totalProducts = productsData?.count ?? 0;
  const lowStockCount = dashboardData?.low_stock_count ?? lowStockData?.count ?? 0;
  const totalCategories = categoriesData?.count ?? 0;

  const stockValue = allProducts.reduce(
    (sum, p) => sum + parseFloat(p.cost_price || "0") * parseFloat(p.stock_quantity || "0"),
    0
  );

  const kpis = [
    { label: "Total Products", value: String(totalProducts), sub: "Across all categories", color: "emerald" },
    { label: "Low Stock Items", value: String(lowStockCount), sub: "Below reorder level", color: "red" },
    { label: "Stock Value", value: formatCurrency(stockValue), sub: "At cost price", color: "blue" },
    { label: "Categories", value: String(totalCategories), sub: "Active categories", color: "violet" },
  ];

  return (
    <div className="space-y-6 max-w-[1400px]">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight">
            Inventory
          </h1>
          <p className="text-sm text-gray-500 mt-1">Product catalog, stock levels, and supplier management</p>
        </div>
        <div className="flex items-center gap-3">
          <button className="px-4 py-2.5 rounded-xl border border-gray-200 bg-white text-sm font-semibold text-gray-700 hover:bg-gray-50 transition-all shadow-sm">
            Stock In
          </button>
          <button className="px-4 py-2.5 rounded-xl bg-black text-white text-sm font-semibold hover:bg-zinc-800 transition-all shadow-sm">
            + Add Product
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis.map((stat) => {
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

      {/* Products Table */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <h2 className="text-lg font-bold text-gray-900">Products</h2>
          <div className="flex items-center gap-3">
            <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
              {(["all", "low"] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilterStatus(f)}
                  className={cn(
                    "px-3 py-1.5 rounded-md text-xs font-semibold transition-all",
                    filterStatus === f ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
                  )}
                >
                  {f === "all" ? "All" : "Low Stock"}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2 bg-gray-100 rounded-lg px-3 py-2">
              <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
              <input
                type="text"
                placeholder="Search products..."
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
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Product</th>
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">SKU</th>
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Category</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Stock</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Reorder</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Cost</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Price</th>
                <th className="text-center px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {productsLoading ? (
                <tr><td colSpan={8} className="px-6 py-8 text-center text-gray-400">Loading products...</td></tr>
              ) : displayProducts.length === 0 ? (
                <tr><td colSpan={8} className="px-6 py-8 text-center text-gray-400">No products found</td></tr>
              ) : (
                displayProducts.map((product: Product) => {
                  const stock = parseFloat(product.stock_quantity || "0");
                  const reorder = parseFloat(product.reorder_level || "0");
                  const isLow = product.is_low_stock;
                  return (
                    <tr key={product.id} className="hover:bg-gray-50/50 transition-colors">
                      <td className="px-6 py-3 font-semibold text-gray-900">{product.name}</td>
                      <td className="px-6 py-3">
                        <span className="px-2 py-1 rounded-md bg-gray-100 text-gray-600 text-xs font-mono">{product.sku}</span>
                      </td>
                      <td className="px-6 py-3 text-gray-600">{product.category_name}</td>
                      <td className={cn("px-6 py-3 text-right font-bold", isLow ? "text-red-600" : "text-gray-900")}>
                        {stock}
                      </td>
                      <td className="px-6 py-3 text-right text-gray-400">{reorder}</td>
                      <td className="px-6 py-3 text-right text-gray-600">UGX {parseFloat(product.cost_price).toLocaleString()}</td>
                      <td className="px-6 py-3 text-right font-semibold text-gray-900">UGX {parseFloat(product.selling_price).toLocaleString()}</td>
                      <td className="px-6 py-3 text-center">
                        <span className={cn(
                          "px-2.5 py-1 rounded-full text-xs font-semibold",
                          isLow ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700"
                        )}>{isLow ? "Low Stock" : "In Stock"}</span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Stock Movements + Categories */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Stock Movements */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="text-lg font-bold text-gray-900">Recent Stock Movements</h2>
          </div>
          <div className="divide-y divide-gray-50">
            {auditLogs.length === 0 ? (
              <div className="px-6 py-8 text-center text-gray-400">No stock movements yet</div>
            ) : (
              auditLogs.slice(0, 8).map((log: StockAuditLog) => {
                const badge = movementBadge(log.movement_type);
                const qtyChange = parseFloat(log.quantity_change);
                const isPositive = qtyChange > 0;
                return (
                  <div key={log.id} className="px-6 py-3.5 flex items-center justify-between hover:bg-gray-50/50 transition-colors">
                    <div className="flex items-center gap-3">
                      <div className={cn("w-9 h-9 rounded-lg flex items-center justify-center text-xs font-bold flex-shrink-0", badge.cls)}>
                        {badge.label}
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-gray-900">{log.product_name}</p>
                        <p className="text-xs text-gray-400">
                          {log.reference_type && `${log.reference_type} #${log.reference_id}`}
                          {log.outlet_name && ` \u00b7 ${log.outlet_name}`}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className={cn("text-sm font-bold", isPositive ? "text-emerald-600" : "text-red-600")}>
                        {isPositive ? "+" : ""}{qtyChange}
                      </p>
                      <p className="text-xs text-gray-400">{new Date(log.created_at).toLocaleDateString()}</p>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Categories */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <h2 className="text-lg font-bold text-gray-900">Categories</h2>
          </div>
          <div className="p-5 space-y-3">
            {categories.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-4">No categories yet</p>
            ) : (
              categories.slice(0, 8).map((cat) => (
                <div key={cat.id} className="flex items-center gap-4 p-3 rounded-xl bg-gray-50 hover:bg-gray-100 transition-colors">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-900">{cat.name}</p>
                    <p className="text-xs text-gray-400">{cat.business_unit}</p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Suppliers */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-lg font-bold text-gray-900">Suppliers</h2>
          <span className="text-sm text-gray-400">{suppliers.length} total</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50">
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Supplier</th>
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Contact</th>
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Email</th>
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Phone</th>
                <th className="text-center px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {suppliers.length === 0 ? (
                <tr><td colSpan={5} className="px-6 py-8 text-center text-gray-400">No suppliers yet</td></tr>
              ) : (
                suppliers.map((supplier) => (
                  <tr key={supplier.id} className="hover:bg-gray-50/50 transition-colors">
                    <td className="px-6 py-3 font-semibold text-gray-900">{supplier.name}</td>
                    <td className="px-6 py-3 text-gray-600">{supplier.contact_person || "—"}</td>
                    <td className="px-6 py-3 text-gray-600">{supplier.email || "—"}</td>
                    <td className="px-6 py-3 text-gray-600">{supplier.phone || "—"}</td>
                    <td className="px-6 py-3 text-center">
                      <span className={cn(
                        "px-2.5 py-1 rounded-full text-xs font-semibold",
                        supplier.is_active ? "bg-emerald-50 text-emerald-700" : "bg-gray-100 text-gray-500"
                      )}>{supplier.is_active ? "Active" : "Inactive"}</span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
