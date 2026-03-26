"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { useSales, useSale, useVoidSale, useSaleReceipt } from "@/lib/hooks/useSales";
import type { Sale } from "@/lib/types";

const STATUS_OPTIONS = [
  { value: "", label: "All Statuses" },
  { value: "completed", label: "Completed" },
  { value: "voided", label: "Voided" },
  { value: "refunded", label: "Refunded" },
];

export default function SalesPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [selectedSaleId, setSelectedSaleId] = useState<number | null>(null);

  const { data, isLoading } = useSales({ search, status: statusFilter, page });
  const { data: saleDetail } = useSale(selectedSaleId || 0);
  const { data: receiptData } = useSaleReceipt(selectedSaleId || 0);
  const voidSale = useVoidSale();

  const totalPages = data ? Math.ceil(data.count / 20) : 0;

  const statusColor = (status: Sale["status"]) => {
    switch (status) {
      case "completed": return "bg-emerald-50 text-emerald-700";
      case "voided": return "bg-red-50 text-red-700";
      case "refunded": return "bg-amber-50 text-amber-700";
    }
  };

  return (
    <div className="space-y-6 max-w-[1400px]">
      {/* Header */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight">Sales History</h1>
        <p className="text-sm text-gray-500 mt-1">View and manage all sales transactions</p>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-3 py-2 flex-1">
          <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input type="text" placeholder="Search by receipt number..." value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} className="bg-transparent text-sm outline-none placeholder-gray-400 w-full" />
        </div>
        <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }} className="bg-white border border-gray-200 rounded-xl px-3 py-2 text-sm text-gray-700">
          {STATUS_OPTIONS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Sales Table */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          {isLoading ? (
            <div className="p-12 text-center text-gray-400">Loading sales...</div>
          ) : !data?.results.length ? (
            <div className="p-12 text-center text-gray-400">No sales found</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50">
                    <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Receipt #</th>
                    <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Total</th>
                    <th className="text-center px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Status</th>
                    <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {data.results.map((sale) => (
                    <tr key={sale.id} onClick={() => setSelectedSaleId(sale.id)} className={cn("hover:bg-gray-50/50 transition-colors cursor-pointer", selectedSaleId === sale.id && "bg-gray-50")}>
                      <td className="px-6 py-3 font-medium text-gray-900">{sale.receipt_number}</td>
                      <td className="px-6 py-3 text-right font-bold text-gray-900">UGX {Number(sale.grand_total).toLocaleString()}</td>
                      <td className="px-6 py-3 text-center">
                        <span className={cn("px-2.5 py-1 rounded-full text-xs font-semibold capitalize", statusColor(sale.status))}>
                          {sale.status}
                        </span>
                      </td>
                      <td className="px-6 py-3 text-right text-gray-400 text-xs">{new Date(sale.created_at).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {totalPages > 1 && (
            <div className="px-6 py-3 border-t border-gray-100 flex items-center justify-between">
              <p className="text-xs text-gray-500">{data?.count} sales total</p>
              <div className="flex gap-1">
                <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="px-3 py-1 rounded-lg text-xs font-medium bg-gray-100 text-gray-600 disabled:opacity-40">Prev</button>
                <span className="px-3 py-1 text-xs text-gray-500">Page {page} of {totalPages}</span>
                <button disabled={page >= totalPages} onClick={() => setPage(page + 1)} className="px-3 py-1 rounded-lg text-xs font-medium bg-gray-100 text-gray-600 disabled:opacity-40">Next</button>
              </div>
            </div>
          )}
        </div>

        {/* Sale Detail Panel */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
          {!selectedSaleId ? (
            <div className="p-8 text-center text-gray-400 text-sm">Select a sale to view details</div>
          ) : !saleDetail ? (
            <div className="p-8 text-center text-gray-400 text-sm">Loading...</div>
          ) : (
            <div>
              <div className="px-5 py-4 border-b border-gray-100">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-bold text-gray-900">{saleDetail.receipt_number}</h2>
                  <span className={cn("px-2.5 py-1 rounded-full text-xs font-semibold capitalize", statusColor(saleDetail.status))}>
                    {saleDetail.status}
                  </span>
                </div>
                <p className="text-xs text-gray-400 mt-1">{new Date(saleDetail.created_at).toLocaleString()}</p>
              </div>

              {/* Items */}
              <div className="px-5 py-3 border-b border-gray-100">
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Items</p>
                <div className="space-y-2">
                  {saleDetail.items.map((item) => (
                    <div key={item.id} className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-gray-900">{item.product_name}</p>
                        <p className="text-xs text-gray-400">{item.quantity} x UGX {Number(item.unit_price).toLocaleString()}</p>
                      </div>
                      <p className="text-sm font-bold text-gray-900">UGX {Number(item.line_total).toLocaleString()}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Totals */}
              <div className="px-5 py-3 border-b border-gray-100 space-y-1">
                <div className="flex justify-between text-sm"><span className="text-gray-500">Subtotal</span><span>UGX {Number(saleDetail.subtotal).toLocaleString()}</span></div>
                <div className="flex justify-between text-sm"><span className="text-gray-500">Tax</span><span>UGX {Number(saleDetail.tax_total).toLocaleString()}</span></div>
                {Number(saleDetail.discount_total) > 0 && (
                  <div className="flex justify-between text-sm"><span className="text-gray-500">Discount</span><span className="text-red-600">-UGX {Number(saleDetail.discount_total).toLocaleString()}</span></div>
                )}
                <div className="flex justify-between text-sm font-bold pt-1 border-t border-gray-100"><span>Grand Total</span><span>UGX {Number(saleDetail.grand_total).toLocaleString()}</span></div>
              </div>

              {/* Payments */}
              <div className="px-5 py-3 border-b border-gray-100">
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Payments</p>
                <div className="space-y-1">
                  {saleDetail.payments.map((p) => (
                    <div key={p.id} className="flex items-center justify-between text-sm">
                      <span className="capitalize text-gray-600">{p.payment_method.replace("_", " ")}</span>
                      <span className="font-medium">UGX {Number(p.amount).toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Actions */}
              {saleDetail.status === "completed" && (
                <div className="p-5">
                  <button
                    onClick={() => { if (confirm("Void this sale? Stock will be restored.")) voidSale.mutate(saleDetail.id); }}
                    disabled={voidSale.isPending}
                    className="w-full px-4 py-2.5 rounded-xl border border-red-200 text-red-600 text-sm font-semibold hover:bg-red-50 disabled:opacity-50"
                  >
                    {voidSale.isPending ? "Voiding..." : "Void Sale"}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
