"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { useShifts, useMyCurrentShift, useOpenShift, useCloseShift } from "@/lib/hooks/useShifts";
import { useOutlets } from "@/lib/hooks/useOutlets";

export default function ShiftsPage() {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [showOpenModal, setShowOpenModal] = useState(false);
  const [showCloseModal, setShowCloseModal] = useState(false);

  const { data: shiftsData, isLoading } = useShifts({ status: statusFilter, page });
  const { data: currentShift, isLoading: currentShiftLoading } = useMyCurrentShift();
  const { data: outletsData } = useOutlets();
  const openShift = useOpenShift();
  const closeShift = useCloseShift();

  const [openForm, setOpenForm] = useState({ outlet: "", opening_cash: "" });
  const [closeForm, setCloseForm] = useState({ closing_cash: "", notes: "" });

  const handleOpenShift = async (e: React.FormEvent) => {
    e.preventDefault();
    await openShift.mutateAsync({ outlet: Number(openForm.outlet), opening_cash: openForm.opening_cash });
    setShowOpenModal(false);
  };

  const handleCloseShift = async (e: React.FormEvent) => {
    e.preventDefault();
    if (currentShift) {
      await closeShift.mutateAsync({ id: currentShift.id, closing_cash: closeForm.closing_cash, notes: closeForm.notes });
      setShowCloseModal(false);
    }
  };

  const totalPages = shiftsData ? Math.ceil(shiftsData.count / 20) : 0;

  return (
    <div className="space-y-6 max-w-[1400px]">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight">Shifts</h1>
          <p className="text-sm text-gray-500 mt-1">Manage cashier shifts and cash reconciliation</p>
        </div>
        {!currentShiftLoading && (
          currentShift ? (
            <button onClick={() => { setCloseForm({ closing_cash: "", notes: "" }); setShowCloseModal(true); }} className="px-4 py-2.5 rounded-xl bg-red-600 text-white text-sm font-semibold hover:bg-red-700 transition-all shadow-sm">
              Close Current Shift
            </button>
          ) : (
            <button onClick={() => { setOpenForm({ outlet: "", opening_cash: "" }); setShowOpenModal(true); }} className="px-4 py-2.5 rounded-xl bg-black text-white text-sm font-semibold hover:bg-zinc-800 transition-all shadow-sm">
              Open Shift
            </button>
          )
        )}
      </div>

      {/* Current Shift Status */}
      {currentShift && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-5">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
            <p className="text-sm font-bold text-emerald-800">Shift Active</p>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-emerald-600">Opened At</p>
              <p className="text-sm font-semibold text-emerald-900">{new Date(currentShift.opened_at).toLocaleTimeString()}</p>
            </div>
            <div>
              <p className="text-xs text-emerald-600">Opening Cash</p>
              <p className="text-sm font-semibold text-emerald-900">UGX {Number(currentShift.opening_cash).toLocaleString()}</p>
            </div>
            {currentShift.expected_cash && (
              <div>
                <p className="text-xs text-emerald-600">Expected Cash</p>
                <p className="text-sm font-semibold text-emerald-900">UGX {Number(currentShift.expected_cash).toLocaleString()}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Filter */}
      <div className="flex gap-3">
        <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }} className="bg-white border border-gray-200 rounded-xl px-3 py-2 text-sm text-gray-700">
          <option value="">All Shifts</option>
          <option value="open">Open</option>
          <option value="closed">Closed</option>
        </select>
      </div>

      {/* Shifts Table */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center text-gray-400">Loading shifts...</div>
        ) : !shiftsData?.results.length ? (
          <div className="p-12 text-center text-gray-400">No shifts found</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50">
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Shift ID</th>
                  <th className="text-center px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Status</th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Opening</th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Closing</th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Expected</th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Opened</th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Closed</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {shiftsData.results.map((shift) => {
                  const variance = shift.closing_cash && shift.expected_cash
                    ? Number(shift.closing_cash) - Number(shift.expected_cash)
                    : null;
                  return (
                    <tr key={shift.id} className="hover:bg-gray-50/50 transition-colors">
                      <td className="px-6 py-3 font-medium text-gray-900">#{shift.id}</td>
                      <td className="px-6 py-3 text-center">
                        <span className={cn("px-2.5 py-1 rounded-full text-xs font-semibold", shift.status === "open" ? "bg-emerald-50 text-emerald-700" : "bg-gray-100 text-gray-600")}>
                          {shift.status}
                        </span>
                      </td>
                      <td className="px-6 py-3 text-right text-gray-900">UGX {Number(shift.opening_cash).toLocaleString()}</td>
                      <td className="px-6 py-3 text-right text-gray-900">{shift.closing_cash ? `UGX ${Number(shift.closing_cash).toLocaleString()}` : "-"}</td>
                      <td className="px-6 py-3 text-right">
                        {shift.expected_cash ? `UGX ${Number(shift.expected_cash).toLocaleString()}` : "-"}
                        {variance !== null && (
                          <span className={cn("ml-1 text-xs font-medium", variance >= 0 ? "text-emerald-600" : "text-red-600")}>
                            ({variance >= 0 ? "+" : ""}{variance.toLocaleString()})
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-3 text-right text-gray-400 text-xs">{new Date(shift.opened_at).toLocaleString()}</td>
                      <td className="px-6 py-3 text-right text-gray-400 text-xs">{shift.closed_at ? new Date(shift.closed_at).toLocaleString() : "-"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {totalPages > 1 && (
          <div className="px-6 py-3 border-t border-gray-100 flex items-center justify-between">
            <p className="text-xs text-gray-500">{shiftsData?.count} shifts total</p>
            <div className="flex gap-1">
              <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="px-3 py-1 rounded-lg text-xs font-medium bg-gray-100 text-gray-600 disabled:opacity-40">Prev</button>
              <span className="px-3 py-1 text-xs text-gray-500">Page {page} of {totalPages}</span>
              <button disabled={page >= totalPages} onClick={() => setPage(page + 1)} className="px-3 py-1 rounded-lg text-xs font-medium bg-gray-100 text-gray-600 disabled:opacity-40">Next</button>
            </div>
          </div>
        )}
      </div>

      {/* Open Shift Modal */}
      {showOpenModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setShowOpenModal(false)}>
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-bold text-gray-900 mb-4">Open Shift</h2>
            <form onSubmit={handleOpenShift} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Outlet</label>
                <select value={openForm.outlet} onChange={(e) => setOpenForm({ ...openForm, outlet: e.target.value })} required className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm">
                  <option value="">Select outlet...</option>
                  {outletsData?.results.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Opening Cash (UGX)</label>
                <input type="number" step="0.01" value={openForm.opening_cash} onChange={(e) => setOpenForm({ ...openForm, opening_cash: e.target.value })} required placeholder="e.g. 50000" className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-black/10" />
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowOpenModal(false)} className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 text-sm font-medium text-gray-600 hover:bg-gray-50">Cancel</button>
                <button type="submit" disabled={openShift.isPending} className="flex-1 px-4 py-2.5 rounded-xl bg-black text-white text-sm font-semibold hover:bg-zinc-800 disabled:opacity-50">
                  {openShift.isPending ? "Opening..." : "Open Shift"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Close Shift Modal */}
      {showCloseModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setShowCloseModal(false)}>
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-lg font-bold text-gray-900 mb-4">Close Shift</h2>
            <form onSubmit={handleCloseShift} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Closing Cash Count (UGX)</label>
                <input type="number" step="0.01" value={closeForm.closing_cash} onChange={(e) => setCloseForm({ ...closeForm, closing_cash: e.target.value })} required placeholder="Count the cash drawer" className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-black/10" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Notes (optional)</label>
                <textarea value={closeForm.notes} onChange={(e) => setCloseForm({ ...closeForm, notes: e.target.value })} placeholder="Any notes about the shift..." className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-black/10" rows={3} />
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowCloseModal(false)} className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 text-sm font-medium text-gray-600 hover:bg-gray-50">Cancel</button>
                <button type="submit" disabled={closeShift.isPending} className="flex-1 px-4 py-2.5 rounded-xl bg-red-600 text-white text-sm font-semibold hover:bg-red-700 disabled:opacity-50">
                  {closeShift.isPending ? "Closing..." : "Close Shift"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
