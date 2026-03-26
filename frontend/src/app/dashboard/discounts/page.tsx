"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { useDiscounts, useCreateDiscount, useUpdateDiscount, useDeleteDiscount } from "@/lib/hooks/useDiscounts";
import type { Discount } from "@/lib/types";

export default function DiscountsPage() {
  const [typeFilter, setTypeFilter] = useState("");
  const [page, setPage] = useState(1);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState<Discount | null>(null);

  const { data, isLoading } = useDiscounts({ discount_type: typeFilter, page });
  const createDiscount = useCreateDiscount();
  const updateDiscount = useUpdateDiscount();
  const deleteDiscount = useDeleteDiscount();

  const [form, setForm] = useState({
    name: "",
    discount_type: "percentage" as Discount["discount_type"],
    value: "",
    is_active: true,
    valid_from: "",
    valid_until: "",
  });

  const openCreate = () => {
    setEditing(null);
    setForm({ name: "", discount_type: "percentage", value: "", is_active: true, valid_from: "", valid_until: "" });
    setShowModal(true);
  };

  const openEdit = (d: Discount) => {
    setEditing(d);
    setForm({
      name: d.name,
      discount_type: d.discount_type,
      value: d.value,
      is_active: d.is_active,
      valid_from: d.valid_from || "",
      valid_until: d.valid_until || "",
    });
    setShowModal(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = {
      ...form,
      valid_from: form.valid_from || null,
      valid_until: form.valid_until || null,
    };
    if (editing) {
      await updateDiscount.mutateAsync({ id: editing.id, ...payload });
    } else {
      await createDiscount.mutateAsync(payload);
    }
    setShowModal(false);
  };

  const totalPages = data ? Math.ceil(data.count / 20) : 0;

  return (
    <div className="space-y-6 max-w-[1400px]">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight">Discounts</h1>
          <p className="text-sm text-gray-500 mt-1">Manage discount rules for sales</p>
        </div>
        <button onClick={openCreate} className="px-4 py-2.5 rounded-xl bg-black text-white text-sm font-semibold hover:bg-zinc-800 transition-all shadow-sm">
          + New Discount
        </button>
      </div>

      {/* Filter */}
      <div className="flex gap-3">
        <select value={typeFilter} onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }} className="bg-white border border-gray-200 rounded-xl px-3 py-2 text-sm text-gray-700">
          <option value="">All Types</option>
          <option value="percentage">Percentage</option>
          <option value="fixed">Fixed Amount</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-gray-400">Loading discounts...</div>
        ) : !data?.results.length ? (
          <div className="p-12 text-center text-gray-400">No discounts found</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50">
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Name</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Type</th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Value</th>
                  <th className="text-center px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Status</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Valid Period</th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {data.results.map((discount) => (
                  <tr key={discount.id} className="hover:bg-gray-50/50 transition-colors">
                    <td className="px-6 py-3 font-medium text-gray-900">{discount.name}</td>
                    <td className="px-6 py-3">
                      <span className={cn("px-2.5 py-1 rounded-full text-xs font-semibold", discount.discount_type === "percentage" ? "bg-blue-50 text-blue-700" : "bg-violet-50 text-violet-700")}>
                        {discount.discount_type}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-right font-bold text-gray-900">
                      {discount.discount_type === "percentage" ? `${discount.value}%` : `UGX ${Number(discount.value).toLocaleString()}`}
                    </td>
                    <td className="px-6 py-3 text-center">
                      <span className={cn("px-2.5 py-1 rounded-full text-xs font-semibold", discount.is_active ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700")}>
                        {discount.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-gray-600 text-xs">
                      {discount.valid_from || discount.valid_until
                        ? `${discount.valid_from ? new Date(discount.valid_from).toLocaleDateString() : "..."} - ${discount.valid_until ? new Date(discount.valid_until).toLocaleDateString() : "..."}`
                        : "Always"}
                    </td>
                    <td className="px-6 py-3 text-right">
                      <button onClick={() => openEdit(discount)} className="text-gray-400 hover:text-gray-700 text-xs font-medium mr-3">Edit</button>
                      <button onClick={() => { if (confirm("Delete this discount?")) deleteDiscount.mutate(discount.id); }} className="text-gray-400 hover:text-red-600 text-xs font-medium">Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {totalPages > 1 && (
          <div className="px-6 py-3 border-t border-gray-100 flex items-center justify-between">
            <p className="text-xs text-gray-500">{data?.count} discounts total</p>
            <div className="flex gap-1">
              <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="px-3 py-1 rounded-lg text-xs font-medium bg-gray-100 text-gray-600 disabled:opacity-40">Prev</button>
              <span className="px-3 py-1 text-xs text-gray-500">Page {page} of {totalPages}</span>
              <button disabled={page >= totalPages} onClick={() => setPage(page + 1)} className="px-3 py-1 rounded-lg text-xs font-medium bg-gray-100 text-gray-600 disabled:opacity-40">Next</button>
            </div>
          </div>
        )}
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setShowModal(false)}>
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-bold text-gray-900 mb-4">{editing ? "Edit Discount" : "New Discount"}</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-black/10" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
                  <select value={form.discount_type} onChange={(e) => setForm({ ...form, discount_type: e.target.value as Discount["discount_type"] })} className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm">
                    <option value="percentage">Percentage</option>
                    <option value="fixed">Fixed Amount</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Value</label>
                  <input type="number" step="0.01" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} required placeholder={form.discount_type === "percentage" ? "e.g. 10" : "e.g. 5000"} className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-black/10" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Valid From</label>
                  <input type="datetime-local" value={form.valid_from} onChange={(e) => setForm({ ...form, valid_from: e.target.value })} className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-black/10" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Valid Until</label>
                  <input type="datetime-local" value={form.valid_until} onChange={(e) => setForm({ ...form, valid_until: e.target.value })} className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-black/10" />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <input type="checkbox" id="is_active" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} className="rounded" />
                <label htmlFor="is_active" className="text-sm text-gray-700">Active</label>
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowModal(false)} className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 text-sm font-medium text-gray-600 hover:bg-gray-50">Cancel</button>
                <button type="submit" disabled={createDiscount.isPending || updateDiscount.isPending} className="flex-1 px-4 py-2.5 rounded-xl bg-black text-white text-sm font-semibold hover:bg-zinc-800 disabled:opacity-50">
                  {createDiscount.isPending || updateDiscount.isPending ? "Saving..." : "Save"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
