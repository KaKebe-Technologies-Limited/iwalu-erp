"use client";

import { useState, FormEvent } from "react";
import { cn } from "@/lib/utils";
import {
  useAccounts,
  useJournalEntries,
  useCreateJournalEntry,
  usePostJournalEntry,
  useVoidJournalEntry,
  useProfitLoss,
  useTrialBalance,
} from "@/lib/hooks/useFinance";
import type { Account, JournalEntry, TrialBalanceLine, ProfitLoss } from "@/lib/types";

// ── Helpers ──────────────────────────────────────────────────────────────────

function today() {
  return new Date().toISOString().split("T")[0];
}

function firstDayOfMonth() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}

function formatCurrency(value: string | number): string {
  const num = parseFloat(String(value));
  if (isNaN(num)) return "UGX 0";
  const abs = Math.abs(num);
  const sign = num < 0 ? "-" : "";
  if (abs >= 1_000_000_000) return `${sign}UGX ${(abs / 1_000_000_000).toFixed(1)}B`;
  if (abs >= 1_000_000) return `${sign}UGX ${(abs / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${sign}UGX ${(abs / 1_000).toFixed(0)}K`;
  return `${sign}UGX ${Math.round(abs).toLocaleString()}`;
}

function entryTotalDebit(entry: JournalEntry) {
  return entry.lines.reduce((s, l) => s + parseFloat(l.debit || "0"), 0);
}

const typeColor: Record<string, { bg: string; text: string }> = {
  asset: { bg: "bg-blue-50", text: "text-blue-700" },
  liability: { bg: "bg-red-50", text: "text-red-700" },
  equity: { bg: "bg-violet-50", text: "text-violet-700" },
  revenue: { bg: "bg-emerald-50", text: "text-emerald-700" },
  expense: { bg: "bg-amber-50", text: "text-amber-700" },
};

const statusColor: Record<string, { bg: string; text: string }> = {
  draft: { bg: "bg-gray-100", text: "text-gray-700" },
  posted: { bg: "bg-emerald-50", text: "text-emerald-700" },
  voided: { bg: "bg-red-50", text: "text-red-600" },
};

// ── New Entry Modal ───────────────────────────────────────────────────────────

function NewEntryModal({
  open,
  onClose,
  accounts,
}: {
  open: boolean;
  onClose: () => void;
  accounts: Account[];
}) {
  const [date, setDate] = useState(today);
  const [description, setDescription] = useState("");
  const [lines, setLines] = useState([
    { account_id: "", debit: "", credit: "" },
    { account_id: "", debit: "", credit: "" },
  ]);
  const [formError, setFormError] = useState("");
  const createEntry = useCreateJournalEntry();

  const totalDebit = lines.reduce((s, l) => s + parseFloat(l.debit || "0"), 0);
  const totalCredit = lines.reduce((s, l) => s + parseFloat(l.credit || "0"), 0);
  const isBalanced = Math.abs(totalDebit - totalCredit) < 0.01 && totalDebit > 0;

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError("");
    if (!isBalanced) {
      setFormError(`Debits (${formatCurrency(totalDebit)}) must equal credits (${formatCurrency(totalCredit)})`);
      return;
    }
    const validLines = lines.filter(
      (l) => l.account_id && (parseFloat(l.debit || "0") > 0 || parseFloat(l.credit || "0") > 0)
    );
    if (validLines.length < 2) {
      setFormError("At least 2 lines with amounts are required");
      return;
    }
    createEntry.mutate(
      {
        date,
        description,
        lines: validLines.map((l) => ({
          account_id: parseInt(l.account_id),
          debit: l.debit || "0",
          credit: l.credit || "0",
        })),
      },
      {
        onSuccess: () => {
          onClose();
          setDate(today());
          setDescription("");
          setLines([
            { account_id: "", debit: "", credit: "" },
            { account_id: "", debit: "", credit: "" },
          ]);
        },
        onError: (err: Error) => setFormError(err.message),
      }
    );
  }

  function updateLine(i: number, field: string, value: string) {
    const updated = [...lines];
    if (field === "debit" && value) updated[i] = { ...updated[i], debit: value, credit: "" };
    else if (field === "credit" && value) updated[i] = { ...updated[i], credit: value, debit: "" };
    else updated[i] = { ...updated[i], [field]: value };
    setLines(updated);
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6 space-y-4 shadow-xl">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold text-gray-900">New Journal Entry</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">&times;</button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1">Date</label>
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                required
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black"
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1">Description</label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                required
                placeholder="e.g. Monthly fuel purchase"
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black"
              />
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-semibold text-gray-700">Journal Lines</span>
              <button
                type="button"
                onClick={() => setLines([...lines, { account_id: "", debit: "", credit: "" }])}
                className="text-xs font-semibold text-black underline"
              >
                + Add Line
              </button>
            </div>

            <div className="space-y-2">
              <div className="grid grid-cols-12 gap-2 text-xs font-semibold text-gray-400 uppercase tracking-wider px-1">
                <span className="col-span-5">Account</span>
                <span className="col-span-3">Debit</span>
                <span className="col-span-3">Credit</span>
              </div>
              {lines.map((line, i) => (
                <div key={i} className="grid grid-cols-12 gap-2 items-center">
                  <div className="col-span-5">
                    <select
                      value={line.account_id}
                      onChange={(e) => updateLine(i, "account_id", e.target.value)}
                      className="w-full border border-gray-200 rounded-lg px-2 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-black"
                    >
                      <option value="">Select account…</option>
                      {accounts.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.code} — {a.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="col-span-3">
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={line.debit}
                      onChange={(e) => updateLine(i, "debit", e.target.value)}
                      placeholder="0.00"
                      className="w-full border border-gray-200 rounded-lg px-2 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-black"
                    />
                  </div>
                  <div className="col-span-3">
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={line.credit}
                      onChange={(e) => updateLine(i, "credit", e.target.value)}
                      placeholder="0.00"
                      className="w-full border border-gray-200 rounded-lg px-2 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-black"
                    />
                  </div>
                  <div className="col-span-1 flex justify-center">
                    {lines.length > 2 && (
                      <button
                        type="button"
                        onClick={() => setLines(lines.filter((_, j) => j !== i))}
                        className="text-red-400 hover:text-red-600 text-xl leading-none"
                      >
                        &times;
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>

            <div className="flex justify-end gap-6 mt-3 text-sm font-semibold border-t border-gray-100 pt-3">
              <span className="text-gray-600">Debit: {formatCurrency(totalDebit)}</span>
              <span className="text-gray-600">Credit: {formatCurrency(totalCredit)}</span>
              <span className={isBalanced ? "text-emerald-600" : "text-red-500"}>
                {isBalanced ? "✓ Balanced" : "Unbalanced"}
              </span>
            </div>
          </div>

          {formError && <p className="text-sm text-red-600 font-medium">{formError}</p>}

          <div className="flex gap-3 justify-end pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg border border-gray-200 text-sm font-semibold text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!isBalanced || createEntry.isPending}
              className="px-4 py-2 rounded-lg bg-black text-white text-sm font-semibold hover:bg-zinc-800 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {createEntry.isPending ? "Creating…" : "Create Entry"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function AccountingPage() {
  const [activeView, setActiveView] = useState<"overview" | "ledger" | "budget" | "tax">("overview");
  const [dateFrom, setDateFrom] = useState(firstDayOfMonth);
  const [dateTo, setDateTo] = useState(today);
  const [showNewEntry, setShowNewEntry] = useState(false);

  const { data: pl, isLoading: plLoading } = useProfitLoss({ date_from: dateFrom, date_to: dateTo });
  const { data: entriesData, isLoading: entriesLoading } = useJournalEntries({ date_from: dateFrom, date_to: dateTo });
  const { data: accountsData } = useAccounts({ is_active: true });
  const { data: trialBalance } = useTrialBalance();
  const postEntry = usePostJournalEntry();
  const voidEntry = useVoidJournalEntry();

  const accounts = accountsData?.results ?? [];
  const entries = entriesData?.results ?? [];
  const liabilityLines = trialBalance?.filter((l) => l.account_type === "liability") ?? [];

  return (
    <>
      <NewEntryModal
        open={showNewEntry}
        onClose={() => setShowNewEntry(false)}
        accounts={accounts}
      />

      <div className="space-y-6 max-w-[1400px]">
        {/* Header */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight">
              Accounting
            </h1>
            <p className="text-sm text-gray-500 mt-1">General ledger, journal entries, and financial reports</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-black"
              />
              <span className="text-gray-400 text-sm">to</span>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-black"
              />
            </div>
            <button
              onClick={() => setShowNewEntry(true)}
              className="px-4 py-2.5 rounded-xl bg-black text-white text-sm font-semibold hover:bg-zinc-800 transition-all shadow-sm whitespace-nowrap"
            >
              + New Entry
            </button>
          </div>
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

        {activeView === "overview" && (
          <OverviewView
            pl={pl}
            plLoading={plLoading}
            entries={entries}
            entriesLoading={entriesLoading}
            entriesCount={entriesData?.count ?? 0}
            onPost={(id) => postEntry.mutate(id)}
            onVoid={(id) => voidEntry.mutate(id)}
          />
        )}
        {activeView === "ledger" && <LedgerView accounts={accounts} />}
        {activeView === "budget" && <BudgetView />}
        {activeView === "tax" && <TaxView lines={liabilityLines} />}
      </div>
    </>
  );
}

// ── Overview ──────────────────────────────────────────────────────────────────

function OverviewView({
  pl,
  plLoading,
  entries,
  entriesLoading,
  entriesCount,
  onPost,
  onVoid,
}: {
  pl: ProfitLoss | undefined;
  plLoading: boolean;
  entries: JournalEntry[];
  entriesLoading: boolean;
  entriesCount: number;
  onPost: (id: number) => void;
  onVoid: (id: number) => void;
}) {
  const revenue = parseFloat(pl?.total_revenue || "0");
  const expenses = parseFloat(pl?.total_expenses || "0");
  const net = parseFloat(pl?.net_income || "0");
  const margin = revenue > 0 ? ((net / revenue) * 100).toFixed(1) : "0.0";

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-2xl p-5 border border-gray-100 shadow-sm">
          <p className="text-sm font-medium text-gray-500">Total Revenue</p>
          <p className="text-2xl font-extrabold text-gray-900 mt-1">
            {plLoading ? "—" : formatCurrency(revenue)}
          </p>
          <p className="text-xs text-gray-400 mt-1">All revenue accounts</p>
        </div>
        <div className="bg-white rounded-2xl p-5 border border-gray-100 shadow-sm">
          <p className="text-sm font-medium text-gray-500">Total Expenses</p>
          <p className="text-2xl font-extrabold text-gray-900 mt-1">
            {plLoading ? "—" : formatCurrency(expenses)}
          </p>
          <p className="text-xs text-gray-400 mt-1">All expense accounts</p>
        </div>
        <div className={cn("rounded-2xl p-5 shadow-sm", net >= 0 ? "bg-emerald-50 border border-emerald-100" : "bg-red-50 border border-red-100")}>
          <p className={cn("text-sm font-medium", net >= 0 ? "text-emerald-700" : "text-red-700")}>
            Net {net >= 0 ? "Profit" : "Loss"}
          </p>
          <p className="text-2xl font-extrabold text-gray-900 mt-1">
            {plLoading ? "—" : formatCurrency(Math.abs(net))}
          </p>
          <p className="text-xs text-gray-500 mt-1">{margin}% margin</p>
        </div>
      </div>

      {/* P&L Breakdown */}
      {!plLoading && pl && (
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <h2 className="text-lg font-bold text-gray-900 mb-4">
            Profit & Loss — {pl.date_from} to {pl.date_to}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="rounded-2xl bg-emerald-50 p-5">
              <p className="text-sm font-semibold text-emerald-700 mb-3">Revenue</p>
              <div className="space-y-2">
                {pl.revenue.length === 0 ? (
                  <p className="text-sm text-gray-400 italic">No revenue posted for this period</p>
                ) : pl.revenue.map((r) => (
                  <div key={r.account_code} className="flex justify-between text-sm">
                    <span className="text-gray-600">{r.account_name}</span>
                    <span className="font-semibold text-gray-900">{formatCurrency(r.amount)}</span>
                  </div>
                ))}
                <div className="border-t border-emerald-200 pt-2 mt-2 flex justify-between text-sm font-bold">
                  <span>Total Revenue</span>
                  <span className="text-emerald-700">{formatCurrency(pl.total_revenue)}</span>
                </div>
              </div>
            </div>
            <div className="rounded-2xl bg-red-50 p-5">
              <p className="text-sm font-semibold text-red-700 mb-3">Expenses</p>
              <div className="space-y-2">
                {pl.expenses.length === 0 ? (
                  <p className="text-sm text-gray-400 italic">No expenses posted for this period</p>
                ) : pl.expenses.map((r) => (
                  <div key={r.account_code} className="flex justify-between text-sm">
                    <span className="text-gray-600">{r.account_name}</span>
                    <span className="font-semibold text-gray-900">{formatCurrency(r.amount)}</span>
                  </div>
                ))}
                <div className="border-t border-red-200 pt-2 mt-2 flex justify-between text-sm font-bold">
                  <span>Total Expenses</span>
                  <span className="text-red-700">{formatCurrency(pl.total_expenses)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Journal Entries */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-lg font-bold text-gray-900">Journal Entries</h2>
          <span className="text-xs text-gray-400">
            {entriesLoading ? "Loading…" : `${entriesCount} entries`}
          </span>
        </div>
        {entries.length === 0 && !entriesLoading ? (
          <p className="px-6 py-8 text-sm text-gray-400 italic text-center">
            No journal entries for this period
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50">
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Entry #</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Date</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Description</th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Amount</th>
                  <th className="text-center px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Status</th>
                  <th className="text-center px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {entries.map((entry) => {
                  const sc = statusColor[entry.status] ?? statusColor.draft;
                  const amount = entryTotalDebit(entry);
                  return (
                    <tr key={entry.id} className="hover:bg-gray-50/50 transition-colors">
                      <td className="px-6 py-3 font-mono text-xs font-bold text-gray-700">{entry.entry_number}</td>
                      <td className="px-6 py-3 text-gray-500 whitespace-nowrap">{entry.date}</td>
                      <td className="px-6 py-3 text-gray-900 max-w-[260px] truncate">{entry.description}</td>
                      <td className="px-6 py-3 text-right font-semibold text-gray-900">
                        {amount > 0 ? formatCurrency(amount) : "—"}
                      </td>
                      <td className="px-6 py-3 text-center">
                        <span className={cn("px-2.5 py-1 rounded-full text-xs font-semibold capitalize", sc.bg, sc.text)}>
                          {entry.status}
                        </span>
                      </td>
                      <td className="px-6 py-3 text-center">
                        <div className="flex items-center justify-center gap-2">
                          {entry.status === "draft" && (
                            <button
                              onClick={() => onPost(entry.id)}
                              className="px-2.5 py-1 rounded-lg bg-emerald-50 text-emerald-700 text-xs font-semibold hover:bg-emerald-100 transition-colors"
                            >
                              Post
                            </button>
                          )}
                          {entry.status === "posted" && (
                            <button
                              onClick={() => onVoid(entry.id)}
                              className="px-2.5 py-1 rounded-lg bg-red-50 text-red-600 text-xs font-semibold hover:bg-red-100 transition-colors"
                            >
                              Void
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Chart of Accounts ─────────────────────────────────────────────────────────

function LedgerView({ accounts }: { accounts: Account[] }) {
  return (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-900">Chart of Accounts</h2>
          <p className="text-sm text-gray-500 mt-1">{accounts.length} accounts in the general ledger</p>
        </div>
        {accounts.length === 0 ? (
          <p className="px-6 py-8 text-sm text-gray-400 italic text-center">
            No accounts found. Run <code className="bg-gray-100 px-1 rounded">seed_chart_of_accounts</code> to initialise.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50">
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Code</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Account Name</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Type</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Parent</th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Sub-accounts</th>
                  <th className="text-center px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {accounts.map((account) => {
                  const tc = typeColor[account.account_type];
                  return (
                    <tr key={account.id} className="hover:bg-gray-50/50 transition-colors">
                      <td className="px-6 py-3">
                        <span className="px-2 py-1 rounded-md bg-gray-100 text-gray-700 text-xs font-mono font-bold">
                          {account.code}
                        </span>
                      </td>
                      <td className="px-6 py-3">
                        <span className="font-semibold text-gray-900">{account.name}</span>
                        {account.is_system && (
                          <span className="ml-2 text-xs text-gray-400 font-normal">system</span>
                        )}
                      </td>
                      <td className="px-6 py-3">
                        <span className={cn("px-2.5 py-1 rounded-full text-xs font-semibold capitalize", tc.bg, tc.text)}>
                          {account.account_type}
                        </span>
                      </td>
                      <td className="px-6 py-3 text-gray-500 text-xs">{account.parent_name ?? "—"}</td>
                      <td className="px-6 py-3 text-right text-gray-500">{account.children_count}</td>
                      <td className="px-6 py-3 text-center">
                        <span className={cn(
                          "px-2.5 py-1 rounded-full text-xs font-semibold",
                          account.is_active ? "bg-emerald-50 text-emerald-700" : "bg-gray-100 text-gray-500"
                        )}>
                          {account.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Budget (placeholder) ──────────────────────────────────────────────────────

function BudgetView() {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-12 text-center space-y-3">
      <div className="text-4xl">📊</div>
      <h3 className="text-lg font-bold text-gray-900">Budget Tracking Coming Soon</h3>
      <p className="text-sm text-gray-500 max-w-md mx-auto">
        Budget management requires a budget model in the backend. Once implemented, you&apos;ll be
        able to set monthly budgets per expense category and track variance against actuals.
      </p>
    </div>
  );
}

// ── Tax & Compliance ──────────────────────────────────────────────────────────

function TaxView({ lines }: { lines: TrialBalanceLine[] }) {
  const safeLines = lines;

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-900">Liability Balances</h2>
          <p className="text-sm text-gray-500 mt-1">Tax payable and other liabilities from the trial balance</p>
        </div>
        {safeLines.length === 0 ? (
          <p className="px-6 py-8 text-sm text-gray-400 italic text-center">No liability balances found</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50">
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Code</th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Account</th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Debit</th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Credit</th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Balance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {safeLines.map((line) => (
                  <tr key={line.account_id} className="hover:bg-gray-50/50 transition-colors">
                    <td className="px-6 py-3">
                      <span className="px-2 py-1 rounded-md bg-gray-100 text-gray-700 text-xs font-mono font-bold">
                        {line.account_code}
                      </span>
                    </td>
                    <td className="px-6 py-3 font-semibold text-gray-900">{line.account_name}</td>
                    <td className="px-6 py-3 text-right text-gray-600">{formatCurrency(line.debit)}</td>
                    <td className="px-6 py-3 text-right text-gray-600">{formatCurrency(line.credit)}</td>
                    <td className="px-6 py-3 text-right font-bold text-red-600">{formatCurrency(line.balance)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="bg-amber-50 rounded-2xl p-5 border border-amber-100">
        <h3 className="text-sm font-bold text-amber-800 mb-1">Note on Tax Compliance</h3>
        <p className="text-xs text-amber-700">
          Tax obligations (VAT 18%, PAYE, NSSF) are tracked as liability accounts in the general ledger.
          Liabilities with a credit balance represent amounts owed. Monitor accounts 2100 (Tax Payable)
          and payroll-related liabilities to ensure timely remittance to URA and NSSF.
        </p>
      </div>
    </div>
  );
}
