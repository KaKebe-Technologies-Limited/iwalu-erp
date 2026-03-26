"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { useOutlets, useCreateOutlet, useUpdateOutlet, useDeleteOutlet } from "@/lib/hooks/useOutlets";
import type { Outlet } from "@/lib/types";

const OUTLET_TYPES = [
  { value: "", label: "All Types" },
  { value: "fuel_station", label: "Fuel Station" },
  { value: "cafe", label: "Cafe" },
  { value: "supermarket", label: "Supermarket" },
  { value: "boutique", label: "Boutique" },
  { value: "bridal", label: "Bridal" },
  { value: "general", label: "General" },
];

export default function OutletsPage() {
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [page, setPage] = useState(1);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState<Outlet | null>(null);

  const { data, isLoading, error } = useOutlets({ search, outlet_type: typeFilter, page });
  const createOutlet = useCreateOutlet();
  const updateOutlet = useUpdateOutlet();
  const deleteOutlet = useDeleteOutlet();

  const [form, setForm] = useState({ name: "", outlet_type: "general" as Outlet["outlet_type"], address: "", phone: "" });

  const openCreate = () => {
    setEditing(null);
    setForm({ name: "", outlet_type: "general", address: "", phone: "" });
    setShowModal(true);
  };

  const openEdit = (outlet: Outlet) => {
    setEditing(outlet);
    setForm({ name: outlet.name, outlet_type: outlet.outlet_type, address: outlet.address, phone: outlet.phone });
    setShowModal(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (editing) {
      await updateOutlet.mutateAsync({ id: editing.id, ...form });
    } else {
      await createOutlet.mutateAsync(form);
    }
    setShowModal(false);
  };

  const totalPages = data ? Math.ceil(data.count / 20) : 0;

  return (
    <div className="space-y-6 max-w-[1400px]">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight">Outlets</h1>
          <p className="text-sm text-gray-500 mt-1">Manage your business locations</p>
        </div>
        <button onClick={openCreate} className="px-4 py-2.5 rounded-xl bg-black text-white text-sm font-semibold hover:bg-zinc-800 transition-all shadow-sm">
          + New Outlet
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="flex items-center gap-2 bg-white border border-gray-200 rounded-xl px-3 py-2 flex-1">
          <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Search outlets..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="bg-transparent text-sm outline-none placeholder-gray-400 w-full"
          />
        </div>
        <select
          value={typeFilter}
          onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
          className="bg-white border border-gray-200 rounded-xl px-3 py-2 text-sm text-gray-700"
        >
          {OUTLET_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-gray-400">Loading outlets...</div>
        ) : error ? (
          <div className="p-12 text-center text-red-500">Failed to load outlets</div>
        ) : !data?.results.length ? (
          <div className="p-12 text-center text-gray-400">No outlets found</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50">
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Name</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Type</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Address</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Phone</th>
                  <th className="text-center px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Status</th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {data.results.map((outlet) => (
                  <tr key={outlet.id} className="hover:bg-gray-50/50 transition-colors">
                    <td className="px-6 py-3 font-medium text-gray-900">{outlet.name}</td>
                    <td className="px-6 py-3">
                      <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-gray-100 text-gray-700 capitalize">
                        {outlet.outlet_type.replace("_", " ")}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-gray-600">{outlet.address}</td>
                    <td className="px-6 py-3 text-gray-600">{outlet.phone}</td>
                    <td className="px-6 py-3 text-center">
                      <span className={cn(
                        "px-2.5 py-1 rounded-full text-xs font-semibold",
                        outlet.is_active ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"
                      )}>
                        {outlet.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-right">
                      <button onClick={() => openEdit(outlet)} className="text-gray-400 hover:text-gray-700 text-xs font-medium mr-3">Edit</button>
                      <button onClick={() => { if (confirm("Delete this outlet?")) deleteOutlet.mutate(outlet.id); }} className="text-gray-400 hover:text-red-600 text-xs font-medium">Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="px-6 py-3 border-t border-gray-100 flex items-center justify-between">
            <p className="text-xs text-gray-500">{data?.count} outlets total</p>
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
            <h2 className="text-lg font-bold text-gray-900 mb-4">{editing ? "Edit Outlet" : "New Outlet"}</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-black/10" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
                <select value={form.outlet_type} onChange={(e) => setForm({ ...form, outlet_type: e.target.value as Outlet["outlet_type"] })} className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm">
                  {OUTLET_TYPES.slice(1).map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Address</label>
                <input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-black/10" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
                <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-black/10" />
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowModal(false)} className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 text-sm font-medium text-gray-600 hover:bg-gray-50">Cancel</button>
                <button type="submit" disabled={createOutlet.isPending || updateOutlet.isPending} className="flex-1 px-4 py-2.5 rounded-xl bg-black text-white text-sm font-semibold hover:bg-zinc-800 disabled:opacity-50">
                  {createOutlet.isPending || updateOutlet.isPending ? "Saving..." : "Save"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
