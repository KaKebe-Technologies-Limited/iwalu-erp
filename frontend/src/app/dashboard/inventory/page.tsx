"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

// ── Mock data ───────────────────────────────────────────────────────────────

const inventoryKPIs = [
  { label: "Total Products", value: "248", sub: "Across all categories", color: "emerald" },
  { label: "Low Stock Items", value: "12", sub: "Below reorder level", color: "red" },
  { label: "Stock Value", value: "UGX 186M", sub: "At cost price", color: "blue" },
  { label: "Categories", value: "14", sub: "Active categories", color: "violet" },
];

const products = [
  { name: "Motor Oil 1L (Shell)", sku: "MO-SH-1L", category: "Lubricants", stock: 28, reorder: 50, cost: "UGX 12,000", price: "UGX 16,000", status: "Low Stock" },
  { name: "Bottled Water 500ml", sku: "BW-500", category: "Beverages", stock: 340, reorder: 100, cost: "UGX 800", price: "UGX 1,500", status: "In Stock" },
  { name: "Coca-Cola 500ml", sku: "CC-500", category: "Beverages", stock: 180, reorder: 80, cost: "UGX 1,200", price: "UGX 2,000", status: "In Stock" },
  { name: "Bread (White Loaf)", sku: "BR-WH", category: "Bakery", stock: 12, reorder: 30, cost: "UGX 2,500", price: "UGX 4,000", status: "Low Stock" },
  { name: "Cigarettes (Sportsman)", sku: "CG-SP", category: "Tobacco", stock: 54, reorder: 40, cost: "UGX 3,000", price: "UGX 5,000", status: "In Stock" },
  { name: "Biscuits (Assorted)", sku: "BS-AST", category: "Snacks", stock: 96, reorder: 50, cost: "UGX 1,000", price: "UGX 2,000", status: "In Stock" },
  { name: "Motor Oil 5L (Total)", sku: "MO-TT-5L", category: "Lubricants", stock: 8, reorder: 20, cost: "UGX 48,000", price: "UGX 65,000", status: "Low Stock" },
  { name: "Air Freshener", sku: "AF-001", category: "Car Care", stock: 42, reorder: 20, cost: "UGX 5,000", price: "UGX 8,000", status: "In Stock" },
  { name: "Phone Charger (USB-C)", sku: "PC-USC", category: "Electronics", stock: 15, reorder: 10, cost: "UGX 8,000", price: "UGX 15,000", status: "In Stock" },
  { name: "Milk (Fresh 500ml)", sku: "MK-FR5", category: "Dairy", stock: 6, reorder: 25, cost: "UGX 2,000", price: "UGX 3,500", status: "Low Stock" },
];

const stockMovements = [
  { id: "SM-401", type: "Stock In", product: "Bottled Water 500ml", qty: "+200 units", by: "Moses Kato", date: "Today, 8:30 AM", reference: "PO-0089" },
  { id: "SM-400", type: "Sale", product: "Motor Oil 1L (Shell)", qty: "-3 units", by: "POS Auto", date: "Today, 8:15 AM", reference: "POS-3042" },
  { id: "SM-399", type: "Transfer", product: "Bread (White Loaf)", qty: "-20 units", by: "Sarah Nakamya", date: "Today, 7:00 AM", reference: "TF-0024" },
  { id: "SM-398", type: "Stock In", product: "Coca-Cola 500ml", qty: "+120 units", by: "Moses Kato", date: "Yesterday, 4:00 PM", reference: "PO-0088" },
  { id: "SM-397", type: "Adjustment", product: "Cigarettes (Sportsman)", qty: "-2 units", by: "Sarah Nakamya", date: "Yesterday, 3:30 PM", reference: "ADJ-0012" },
];

const suppliers = [
  { name: "Mukwano Industries", contact: "+256 700 123 456", items: 34, lastOrder: "28 Feb 2026", outstanding: "UGX 2.4M" },
  { name: "Shell Uganda Ltd", contact: "+256 700 234 567", items: 12, lastOrder: "25 Feb 2026", outstanding: "UGX 0" },
  { name: "Century Bottling Co.", contact: "+256 700 345 678", items: 8, lastOrder: "1 Mar 2026", outstanding: "UGX 890K" },
  { name: "Roofings Rolling Mills", contact: "+256 700 456 789", items: 5, lastOrder: "20 Feb 2026", outstanding: "UGX 0" },
];

const categories = [
  { name: "Beverages", count: 42, value: "UGX 8.2M" },
  { name: "Lubricants", count: 18, value: "UGX 45.6M" },
  { name: "Snacks", count: 35, value: "UGX 3.8M" },
  { name: "Car Care", count: 22, value: "UGX 12.4M" },
  { name: "Bakery", count: 8, value: "UGX 1.2M" },
  { name: "Tobacco", count: 6, value: "UGX 2.1M" },
];

const colorMap: Record<string, { bg: string; text: string; light: string }> = {
  emerald: { bg: "bg-emerald-500", text: "text-emerald-600", light: "bg-emerald-50" },
  blue: { bg: "bg-blue-500", text: "text-blue-600", light: "bg-blue-50" },
  violet: { bg: "bg-violet-500", text: "text-violet-600", light: "bg-violet-50" },
  red: { bg: "bg-red-500", text: "text-red-600", light: "bg-red-50" },
};

// ── Component ───────────────────────────────────────────────────────────────

export default function InventoryPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [filterStatus, setFilterStatus] = useState<"all" | "low">("all");

  const filteredProducts = products.filter((p) => {
    const matchSearch = p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.sku.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.category.toLowerCase().includes(searchQuery.toLowerCase());
    const matchFilter = filterStatus === "all" || p.status === "Low Stock";
    return matchSearch && matchFilter;
  });

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
        {inventoryKPIs.map((stat) => {
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
              {filteredProducts.map((product) => (
                <tr key={product.sku} className="hover:bg-gray-50/50 transition-colors">
                  <td className="px-6 py-3 font-semibold text-gray-900">{product.name}</td>
                  <td className="px-6 py-3">
                    <span className="px-2 py-1 rounded-md bg-gray-100 text-gray-600 text-xs font-mono">{product.sku}</span>
                  </td>
                  <td className="px-6 py-3 text-gray-600">{product.category}</td>
                  <td className={cn("px-6 py-3 text-right font-bold", product.stock <= product.reorder ? "text-red-600" : "text-gray-900")}>
                    {product.stock}
                  </td>
                  <td className="px-6 py-3 text-right text-gray-400">{product.reorder}</td>
                  <td className="px-6 py-3 text-right text-gray-600">{product.cost}</td>
                  <td className="px-6 py-3 text-right font-semibold text-gray-900">{product.price}</td>
                  <td className="px-6 py-3 text-center">
                    <span className={cn(
                      "px-2.5 py-1 rounded-full text-xs font-semibold",
                      product.status === "In Stock" ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"
                    )}>{product.status}</span>
                  </td>
                </tr>
              ))}
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
            {stockMovements.map((movement) => (
              <div key={movement.id} className="px-6 py-3.5 flex items-center justify-between hover:bg-gray-50/50 transition-colors">
                <div className="flex items-center gap-3">
                  <div className={cn(
                    "w-9 h-9 rounded-lg flex items-center justify-center text-xs font-bold flex-shrink-0",
                    movement.type === "Stock In" ? "bg-emerald-50 text-emerald-700" :
                    movement.type === "Sale" ? "bg-blue-50 text-blue-700" :
                    movement.type === "Transfer" ? "bg-violet-50 text-violet-700" :
                    "bg-amber-50 text-amber-700"
                  )}>
                    {movement.type === "Stock In" ? "IN" : movement.type === "Sale" ? "S" : movement.type === "Transfer" ? "TF" : "AD"}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-gray-900">{movement.product}</p>
                    <p className="text-xs text-gray-400">{movement.reference} &middot; {movement.by}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className={cn("text-sm font-bold", movement.qty.startsWith("+") ? "text-emerald-600" : "text-red-600")}>
                    {movement.qty}
                  </p>
                  <p className="text-xs text-gray-400">{movement.date}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Categories */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <h2 className="text-lg font-bold text-gray-900">Categories</h2>
          </div>
          <div className="p-5 space-y-3">
            {categories.map((cat) => (
              <div key={cat.name} className="flex items-center gap-4 p-3 rounded-xl bg-gray-50 hover:bg-gray-100 transition-colors">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-gray-900">{cat.name}</p>
                  <p className="text-xs text-gray-400">{cat.count} products</p>
                </div>
                <span className="text-sm font-bold text-gray-900 flex-shrink-0">{cat.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Suppliers */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-lg font-bold text-gray-900">Suppliers</h2>
          <button className="text-sm font-semibold text-gray-500 hover:text-gray-900 transition-colors">View All</button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50">
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Supplier</th>
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Contact</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Items</th>
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Last Order</th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Outstanding</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {suppliers.map((supplier) => (
                <tr key={supplier.name} className="hover:bg-gray-50/50 transition-colors">
                  <td className="px-6 py-3 font-semibold text-gray-900">{supplier.name}</td>
                  <td className="px-6 py-3 text-gray-600">{supplier.contact}</td>
                  <td className="px-6 py-3 text-right text-gray-600">{supplier.items}</td>
                  <td className="px-6 py-3 text-gray-500">{supplier.lastOrder}</td>
                  <td className={cn("px-6 py-3 text-right font-bold", supplier.outstanding === "UGX 0" ? "text-emerald-600" : "text-amber-600")}>
                    {supplier.outstanding}
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
