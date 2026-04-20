"use client";

import { useState, FormEvent } from "react";
import { cn } from "@/lib/utils";
import {
  usePumps,
  useActivatePump,
  useDeactivatePump,
  useSetPumpMaintenance,
  useTankLevelsSummary,
  useRecordTankReading,
  usePumpReadings,
  useFuelDeliveries,
  useCreateFuelDelivery,
  useFuelReconciliations,
  useConfirmReconciliation,
  useVarianceReport,
  useDailyPumpReport,
} from "@/lib/hooks/useFuel";
import type {
  Pump,
  Tank,
  PumpReading,
  FuelDelivery,
  FuelReconciliation,
  DailyPumpReport,
} from "@/lib/types";

const today = () => new Date().toISOString().split("T")[0];
const firstDayOfMonth = () =>
  new Date(new Date().getFullYear(), new Date().getMonth(), 1)
    .toISOString()
    .split("T")[0];

function fmtVol(val: string | number | null | undefined): string {
  if (val === null || val === undefined || val === "") return "—";
  const n = typeof val === "string" ? parseFloat(val) : val;
  if (isNaN(n)) return String(val);
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M L`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K L`;
  return `${n.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 1 })} L`;
}

function fmtCost(val: string | null | undefined): string {
  if (!val) return "—";
  const n = parseFloat(val);
  if (isNaN(n)) return val;
  if (n >= 1_000_000) return `UGX ${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `UGX ${(n / 1_000).toFixed(0)}K`;
  return `UGX ${n.toLocaleString()}`;
}

const statusColor: Record<string, string> = {
  active: "bg-emerald-500",
  inactive: "bg-gray-400",
  maintenance: "bg-red-500",
};
const statusBorder: Record<string, string> = {
  active: "border-emerald-200 bg-emerald-50/50",
  inactive: "border-gray-200 bg-gray-50",
  maintenance: "border-red-200 bg-red-50/50",
};

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function FuelStationPage() {
  const [activeView, setActiveView] = useState<
    "overview" | "reconciliation" | "deliveries"
  >("overview");
  const [showDip, setShowDip] = useState(false);
  const [showDelivery, setShowDelivery] = useState(false);

  return (
    <div className="space-y-6 max-w-[1400px]">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight">
            Fuel Station
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Monitor pumps, tanks, and daily fuel operations
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowDip(true)}
            className="px-4 py-2.5 rounded-xl border border-gray-200 bg-white text-sm font-semibold text-gray-700 hover:bg-gray-50 transition-all shadow-sm"
          >
            Record Dip
          </button>
          <button
            onClick={() => setShowDelivery(true)}
            className="px-4 py-2.5 rounded-xl bg-black text-white text-sm font-semibold hover:bg-zinc-800 transition-all shadow-sm"
          >
            Add Delivery
          </button>
        </div>
      </div>

      {/* View Toggle */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-xl w-fit">
        {(
          [
            ["overview", "Live Overview"],
            ["reconciliation", "Daily Reconciliation"],
            ["deliveries", "Deliveries"],
          ] as const
        ).map(([view, label]) => (
          <button
            key={view}
            onClick={() => setActiveView(view)}
            className={cn(
              "px-4 py-2.5 rounded-lg text-sm font-semibold whitespace-nowrap transition-all",
              activeView === view
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-700",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {activeView === "overview" && <OverviewView />}
      {activeView === "reconciliation" && <ReconciliationView />}
      {activeView === "deliveries" && (
        <DeliveriesView onAdd={() => setShowDelivery(true)} />
      )}

      {showDip && <RecordDipModal onClose={() => setShowDip(false)} />}
      {showDelivery && (
        <AddDeliveryModal onClose={() => setShowDelivery(false)} />
      )}
    </div>
  );
}

// ── Overview View ─────────────────────────────────────────────────────────────

function OverviewView() {
  const reportDate = today();
  const { data: pumpsData, isLoading: pumpsLoading } = usePumps();
  const { data: tankLevels, isLoading: tanksLoading } = useTankLevelsSummary();
  const { data: dailyReport, isLoading: reportLoading } = useDailyPumpReport({
    date: reportDate,
  });
  const { data: readingsData, isLoading: readingsLoading } = usePumpReadings({
    page: 1,
  });

  const pumps = pumpsData?.results ?? [];
  const tanks = tankLevels ?? [];
  const readings = readingsData?.results ?? [];

  const activePumps = pumps.filter((p) => p.status === "active").length;
  const totalPumps = pumps.length;
  const lowTanks = tanks.filter((t) => t.is_low).length;
  const openSessions = readings.filter((r) => !r.closing_reading).length;

  const totalVolToday = dailyReport?.totals_by_product.reduce((sum, t) => {
    return sum + (t.total_volume ? parseFloat(t.total_volume) : 0);
  }, 0);

  const kpis = [
    {
      label: "Volume Today",
      value: reportLoading
        ? "..."
        : totalVolToday !== undefined
          ? fmtVol(totalVolToday)
          : "—",
      sub: `Across ${dailyReport?.totals_by_product.length ?? 0} product(s)`,
      color: "emerald",
    },
    {
      label: "Active Pumps",
      value: pumpsLoading ? "..." : `${activePumps} / ${totalPumps}`,
      sub:
        totalPumps - activePumps > 0
          ? `${totalPumps - activePumps} offline or maintenance`
          : "All pumps operational",
      color: "blue",
    },
    {
      label: "Low Tank Alerts",
      value: tanksLoading ? "..." : String(lowTanks),
      sub: lowTanks > 0 ? "Immediate reorder required" : "All tanks sufficient",
      color: lowTanks > 0 ? "amber" : "violet",
    },
    {
      label: "Open Sessions",
      value: readingsLoading ? "..." : String(openSessions),
      sub: "Pump readings not yet closed",
      color: "amber",
    },
  ];

  const colorMap: Record<
    string,
    { bg: string; text: string; light: string }
  > = {
    emerald: {
      bg: "bg-emerald-500",
      text: "text-emerald-600",
      light: "bg-emerald-50",
    },
    blue: { bg: "bg-blue-500", text: "text-blue-600", light: "bg-blue-50" },
    violet: {
      bg: "bg-violet-500",
      text: "text-violet-600",
      light: "bg-violet-50",
    },
    amber: {
      bg: "bg-amber-500",
      text: "text-amber-600",
      light: "bg-amber-50",
    },
  };

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis.map((stat) => {
          const c = colorMap[stat.color];
          return (
            <div
              key={stat.label}
              className="bg-white rounded-2xl p-5 border border-gray-100 shadow-sm hover:shadow-md transition-shadow"
            >
              <p className="text-sm font-medium text-gray-500">{stat.label}</p>
              <p className="text-2xl font-extrabold text-gray-900 mt-1">
                {stat.value}
              </p>
              <p className="text-xs text-gray-400 mt-1">{stat.sub}</p>
              <div className={cn("mt-3 h-1 rounded-full", c.light)}>
                <div
                  className={cn("h-1 rounded-full", c.bg)}
                  style={{ width: "65%" }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Tank Levels */}
      <TankLevelsSection tanks={tanks} loading={tanksLoading} />

      {/* Pump Status */}
      <PumpStatusSection
        pumps={pumps}
        loading={pumpsLoading}
        dailyReport={dailyReport}
      />

      {/* Recent Pump Sessions */}
      <PumpSessionsTable readings={readings} loading={readingsLoading} />
    </div>
  );
}

function TankLevelsSection({
  tanks,
  loading,
}: {
  tanks: Tank[];
  loading: boolean;
}) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
      <h2 className="text-lg font-bold text-gray-900 mb-5">
        Tank Dip Readings
      </h2>
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="rounded-2xl bg-gray-50 p-5 h-36 animate-pulse"
            />
          ))}
        </div>
      ) : tanks.length === 0 ? (
        <p className="text-sm text-gray-400 italic">No tanks configured.</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {tanks.map((tank) => {
            const pct = Math.round(tank.fill_percentage);
            const levelColors =
              pct >= 50
                ? { bar: "bg-emerald-500", text: "text-gray-900" }
                : pct >= 25
                  ? { bar: "bg-amber-500", text: "text-amber-700" }
                  : { bar: "bg-red-500", text: "text-red-700" };
            return (
              <div
                key={tank.id}
                className="relative rounded-2xl bg-gray-50 p-5 overflow-hidden"
              >
                <div
                  className={cn(
                    "absolute bottom-0 left-0 right-0 opacity-10",
                    levelColors.bar,
                  )}
                  style={{ height: `${pct}%` }}
                />
                <div className="relative">
                  <div className="flex items-start justify-between mb-2">
                    <p className="text-sm font-semibold text-gray-700 leading-tight">
                      {tank.name}
                    </p>
                    <span className="text-xs bg-gray-200 text-gray-600 px-2 py-0.5 rounded-full font-medium">
                      {tank.product_name}
                    </span>
                  </div>
                  <p
                    className={cn(
                      "text-4xl font-extrabold mt-2",
                      levelColors.text,
                    )}
                  >
                    {pct}%
                  </p>
                  <p className="text-sm text-gray-500 mt-1">
                    {fmtVol(tank.current_level)} /{" "}
                    {fmtVol(tank.capacity)}
                  </p>
                  <div className="mt-3 w-full bg-gray-200 rounded-full h-1.5">
                    <div
                      className={cn("h-1.5 rounded-full", levelColors.bar)}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  {tank.is_low && (
                    <div className="mt-3 flex items-center gap-2 text-red-600 text-xs font-semibold">
                      <svg
                        className="w-4 h-4 shrink-0"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z"
                        />
                      </svg>
                      Low level — order required
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function PumpStatusSection({
  pumps,
  loading,
  dailyReport,
}: {
  pumps: Pump[];
  loading: boolean;
  dailyReport: DailyPumpReport | undefined;
}) {
  const activate = useActivatePump();
  const deactivate = useDeactivatePump();
  const setMaintenance = useSetPumpMaintenance();

  const volumeByPump: Record<number, string> = {};
  if (dailyReport) {
    for (const entry of dailyReport.pumps) {
      if (entry.volume_dispensed) {
        volumeByPump[entry.pump_number] = entry.volume_dispensed;
      }
    }
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
      <h2 className="text-lg font-bold text-gray-900 mb-5">Pump Status</h2>
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div
              key={i}
              className="rounded-xl border border-gray-200 p-4 h-28 animate-pulse bg-gray-50"
            />
          ))}
        </div>
      ) : pumps.length === 0 ? (
        <p className="text-sm text-gray-400 italic">No pumps configured.</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {pumps.map((pump) => {
            const dispVol = volumeByPump[pump.pump_number];
            return (
              <div
                key={pump.id}
                className={cn(
                  "rounded-xl border p-4 transition-all",
                  statusBorder[pump.status] ?? "border-gray-200 bg-gray-50",
                )}
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="text-lg font-extrabold text-gray-900">
                    P{pump.pump_number}
                    {pump.name && (
                      <span className="text-sm font-medium text-gray-500 ml-1">
                        {pump.name}
                      </span>
                    )}
                  </span>
                  <span className="flex items-center gap-1.5 text-xs font-semibold text-gray-600">
                    <span
                      className={cn(
                        "w-2 h-2 rounded-full",
                        statusColor[pump.status] ?? "bg-gray-400",
                      )}
                    />
                    {pump.status_display}
                  </span>
                </div>
                <p className="text-xs text-gray-500 font-medium mb-2">
                  {pump.product_name} &middot; {pump.outlet_name}
                </p>
                {pump.status === "active" && dispVol ? (
                  <p className="text-sm text-gray-700">
                    <span className="font-bold text-gray-900">
                      {fmtVol(dispVol)}
                    </span>{" "}
                    dispensed today
                  </p>
                ) : pump.status === "active" ? (
                  <p className="text-sm text-gray-400">No readings today</p>
                ) : (
                  <p className="text-sm text-gray-400 italic">
                    {pump.status === "maintenance"
                      ? "Under maintenance"
                      : "Inactive"}
                  </p>
                )}
                {/* Quick action buttons */}
                <div className="mt-3 pt-2 border-t border-gray-200/60 flex gap-2">
                  {pump.status !== "active" && (
                    <button
                      onClick={() => activate.mutate(pump.id)}
                      disabled={activate.isPending}
                      className="text-xs px-2 py-1 rounded-md bg-emerald-50 text-emerald-700 hover:bg-emerald-100 font-medium transition-colors"
                    >
                      Activate
                    </button>
                  )}
                  {pump.status === "active" && (
                    <button
                      onClick={() => deactivate.mutate(pump.id)}
                      disabled={deactivate.isPending}
                      className="text-xs px-2 py-1 rounded-md bg-gray-100 text-gray-600 hover:bg-gray-200 font-medium transition-colors"
                    >
                      Deactivate
                    </button>
                  )}
                  {pump.status !== "maintenance" && (
                    <button
                      onClick={() => setMaintenance.mutate(pump.id)}
                      disabled={setMaintenance.isPending}
                      className="text-xs px-2 py-1 rounded-md bg-red-50 text-red-600 hover:bg-red-100 font-medium transition-colors"
                    >
                      Set Maintenance
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function PumpSessionsTable({
  readings,
  loading,
}: {
  readings: PumpReading[];
  loading: boolean;
}) {
  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
        <h2 className="text-lg font-bold text-gray-900">
          Recent Pump Sessions
        </h2>
        <span className="text-xs text-gray-400 font-medium">
          Latest 20 sessions
        </span>
      </div>
      {loading ? (
        <div className="p-6 space-y-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-10 rounded-lg bg-gray-100 animate-pulse"
            />
          ))}
        </div>
      ) : readings.length === 0 ? (
        <div className="px-6 py-10 text-center text-sm text-gray-400">
          No pump sessions recorded yet.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50">
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">
                  Pump
                </th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">
                  Opening
                </th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">
                  Closing
                </th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">
                  Dispensed
                </th>
                <th className="text-center px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">
                  Status
                </th>
                <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">
                  Opened
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {readings.map((r) => (
                <tr
                  key={r.id}
                  className="hover:bg-gray-50/50 transition-colors"
                >
                  <td className="px-6 py-3">
                    <span className="font-bold text-gray-900">
                      P{r.pump_number}
                    </span>
                    {r.pump_name && (
                      <span className="text-gray-400 ml-1 text-xs">
                        {r.pump_name}
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-3 text-right text-gray-600">
                    {fmtVol(r.opening_reading)}
                  </td>
                  <td className="px-6 py-3 text-right text-gray-600">
                    {r.closing_reading ? fmtVol(r.closing_reading) : "—"}
                  </td>
                  <td className="px-6 py-3 text-right font-bold text-gray-900">
                    {r.volume_dispensed ? fmtVol(r.volume_dispensed) : "—"}
                  </td>
                  <td className="px-6 py-3 text-center">
                    <span
                      className={cn(
                        "px-2.5 py-1 rounded-full text-xs font-semibold",
                        r.closing_reading
                          ? "bg-emerald-50 text-emerald-700"
                          : "bg-amber-50 text-amber-700",
                      )}
                    >
                      {r.closing_reading ? "Closed" : "Open"}
                    </span>
                  </td>
                  <td className="px-6 py-3 text-right text-gray-400 text-xs">
                    {new Date(r.created_at).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Reconciliation View ───────────────────────────────────────────────────────

function ReconciliationView() {
  const [dateFrom, setDateFrom] = useState(today());
  const [dateTo, setDateTo] = useState(today());

  const { data: recoData, isLoading: recoLoading } = useFuelReconciliations({
    date_from: dateFrom,
    date_to: dateTo,
  });
  const { data: varianceReport, isLoading: varLoading } = useVarianceReport({
    date_from: dateFrom,
    date_to: dateTo,
  });
  const confirm = useConfirmReconciliation();

  const recos = recoData?.results ?? [];
  const summary = varianceReport?.summary;

  const okCount = recos.filter((r) => r.variance_type === "within_tolerance").length;
  const issueCount = recos.filter((r) => r.variance_type !== "within_tolerance").length;

  return (
    <div className="space-y-6">
      {/* Date Range */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-gray-900">
              Daily Fuel Reconciliation
            </h2>
            <p className="text-sm text-gray-500 mt-1">
              Review variance between dispensed and physical dip readings
            </p>
          </div>
          <div className="flex items-end gap-3">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-500">From</label>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="block border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black/10"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-500">To</label>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="block border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-black/10"
              />
            </div>
          </div>
        </div>
        {!recoLoading && recos.length > 0 && (
          <div className="flex items-center gap-3 mt-4 pt-4 border-t border-gray-100">
            <span className="px-3 py-1.5 rounded-full bg-emerald-50 text-emerald-700 text-xs font-semibold">
              {okCount} Within Tolerance
            </span>
            {issueCount > 0 && (
              <span className="px-3 py-1.5 rounded-full bg-amber-50 text-amber-700 text-xs font-semibold">
                {issueCount} Need Review
              </span>
            )}
          </div>
        )}
      </div>

      {/* Reconciliation Table */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        {recoLoading ? (
          <div className="p-6 space-y-3">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-12 rounded-lg bg-gray-100 animate-pulse"
              />
            ))}
          </div>
        ) : recos.length === 0 ? (
          <div className="px-6 py-12 text-center text-sm text-gray-400">
            No reconciliation records for this period.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50">
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">
                    Date
                  </th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">
                    Tank
                  </th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">
                    Opening
                  </th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">
                    Received
                  </th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">
                    Dispensed
                  </th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">
                    Closing
                  </th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">
                    Variance
                  </th>
                  <th className="text-center px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {recos.map((r) => {
                  const varNum = parseFloat(r.variance);
                  const isLoss = r.variance_type === "loss";
                  const isGain = r.variance_type === "gain";
                  return (
                    <tr
                      key={r.id}
                      className="hover:bg-gray-50/50 transition-colors"
                    >
                      <td className="px-6 py-4 text-gray-700 text-xs">
                        {r.date}
                      </td>
                      <td className="px-6 py-4 font-semibold text-gray-900">
                        {r.tank_name}
                      </td>
                      <td className="px-6 py-4 text-right text-gray-600">
                        {fmtVol(r.opening_stock)}
                      </td>
                      <td className="px-6 py-4 text-right text-gray-600">
                        {fmtVol(r.total_received)}
                      </td>
                      <td className="px-6 py-4 text-right font-semibold text-gray-900">
                        {fmtVol(r.total_dispensed)}
                      </td>
                      <td className="px-6 py-4 text-right font-semibold text-gray-900">
                        {fmtVol(r.closing_stock)}
                      </td>
                      <td
                        className={cn(
                          "px-6 py-4 text-right font-bold",
                          isLoss
                            ? "text-red-600"
                            : isGain
                              ? "text-blue-600"
                              : "text-emerald-600",
                        )}
                      >
                        {varNum > 0 ? "+" : ""}
                        {fmtVol(r.variance)}{" "}
                        <span className="font-normal text-xs">
                          ({r.variance_percentage}%)
                        </span>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <span
                          className={cn(
                            "px-2.5 py-1 rounded-full text-xs font-semibold",
                            r.variance_type === "within_tolerance"
                              ? "bg-emerald-50 text-emerald-700"
                              : r.variance_type === "gain"
                                ? "bg-blue-50 text-blue-700"
                                : "bg-red-50 text-red-700",
                          )}
                        >
                          {r.variance_type_display}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        {r.status === "draft" && (
                          <button
                            onClick={() => confirm.mutate(r.id)}
                            disabled={confirm.isPending}
                            className="text-xs px-3 py-1.5 rounded-lg bg-black text-white hover:bg-zinc-800 font-semibold transition-colors disabled:opacity-50"
                          >
                            Confirm
                          </button>
                        )}
                        {r.status === "confirmed" && (
                          <span className="text-xs text-gray-400 font-medium">
                            Confirmed
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Variance Summary */}
      {(summary || varLoading) && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="rounded-2xl bg-emerald-50 p-5">
            <p className="text-sm font-semibold text-emerald-700 mb-3">
              Within Tolerance
            </p>
            <p className="text-3xl font-extrabold text-gray-900">
              {varLoading ? "..." : summary?.within_tolerance_count ?? 0}
            </p>
            <p className="text-sm text-gray-500 mt-1">Reconciliations OK</p>
          </div>
          <div className="rounded-2xl bg-blue-50 p-5">
            <p className="text-sm font-semibold text-blue-700 mb-3">
              Net Variance
            </p>
            <p className="text-3xl font-extrabold text-gray-900">
              {varLoading
                ? "..."
                : summary?.total_variance
                  ? fmtVol(summary.total_variance)
                  : "0 L"}
            </p>
            <p className="text-sm text-gray-500 mt-1">
              {(summary?.loss_count ?? 0) > 0
                ? `${summary?.loss_count} loss • ${summary?.gain_count} gain`
                : "No significant variance"}
            </p>
          </div>
          <div
            className={cn(
              "rounded-2xl p-5",
              (summary?.loss_count ?? 0) > 0 ? "bg-red-50" : "bg-gray-50",
            )}
          >
            <p
              className={cn(
                "text-sm font-semibold mb-3",
                (summary?.loss_count ?? 0) > 0
                  ? "text-red-700"
                  : "text-gray-600",
              )}
            >
              Loss Events
            </p>
            <p className="text-3xl font-extrabold text-gray-900">
              {varLoading ? "..." : summary?.loss_count ?? 0}
            </p>
            <p className="text-sm text-gray-500 mt-1">
              {(summary?.loss_count ?? 0) > 0
                ? "Requires investigation"
                : "No losses recorded"}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Deliveries View ───────────────────────────────────────────────────────────

function DeliveriesView({ onAdd }: { onAdd: () => void }) {
  const { data: deliveriesData, isLoading } = useFuelDeliveries({ page: 1 });
  const deliveries = deliveriesData?.results ?? [];

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-gray-900">
              Fuel Deliveries
            </h2>
            <p className="text-sm text-gray-500 mt-0.5">
              {deliveriesData?.count ?? 0} total records
            </p>
          </div>
          <button
            onClick={onAdd}
            className="px-4 py-2 rounded-xl bg-black text-white text-sm font-semibold hover:bg-zinc-800 transition-all"
          >
            + Add Delivery
          </button>
        </div>
        {isLoading ? (
          <div className="p-6 space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="h-12 rounded-lg bg-gray-100 animate-pulse"
              />
            ))}
          </div>
        ) : deliveries.length === 0 ? (
          <div className="px-6 py-12 text-center text-sm text-gray-400">
            No fuel deliveries recorded yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50">
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">
                    Date
                  </th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">
                    Tank
                  </th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">
                    Supplier
                  </th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">
                    Ordered
                  </th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">
                    Received
                  </th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">
                    Unit Cost
                  </th>
                  <th className="text-right px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">
                    Total Cost
                  </th>
                  <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">
                    Note #
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {deliveries.map((d) => (
                  <tr
                    key={d.id}
                    className="hover:bg-gray-50/50 transition-colors"
                  >
                    <td className="px-6 py-4 text-gray-700 text-xs whitespace-nowrap">
                      {new Date(d.delivery_date).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 font-semibold text-gray-900">
                      {d.tank_name}
                    </td>
                    <td className="px-6 py-4 text-gray-600">
                      {d.supplier_name}
                    </td>
                    <td className="px-6 py-4 text-right text-gray-600">
                      {d.volume_ordered ? fmtVol(d.volume_ordered) : "—"}
                    </td>
                    <td className="px-6 py-4 text-right font-bold text-gray-900">
                      {fmtVol(d.volume_received)}
                    </td>
                    <td className="px-6 py-4 text-right text-gray-600">
                      {fmtCost(d.unit_cost)}/L
                    </td>
                    <td className="px-6 py-4 text-right font-semibold text-gray-900">
                      {fmtCost(d.total_cost)}
                    </td>
                    <td className="px-6 py-4 text-gray-500 text-xs">
                      {d.delivery_note_number || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Record Dip Modal ──────────────────────────────────────────────────────────

function RecordDipModal({ onClose }: { onClose: () => void }) {
  const { data: tankLevels } = useTankLevelsSummary();
  const tanks = tankLevels ?? [];
  const record = useRecordTankReading();

  const [tankId, setTankId] = useState("");
  const [level, setLevel] = useState("");
  const [readingType, setReadingType] = useState("manual");
  const [readingAt, setReadingAt] = useState(
    new Date().toISOString().slice(0, 16),
  );
  const [notes, setNotes] = useState("");

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    await record.mutateAsync({
      tankId: Number(tankId),
      data: {
        reading_level: level,
        reading_type: readingType,
        reading_at: new Date(readingAt).toISOString(),
        notes,
      },
    });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-6 py-5 border-b border-gray-100">
          <h3 className="text-lg font-bold text-gray-900">Record Tank Dip</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-gray-700">Tank</label>
            <select
              required
              value={tankId}
              onChange={(e) => setTankId(e.target.value)}
              className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-black/10"
            >
              <option value="">Select a tank…</option>
              {tanks.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} ({t.product_name}) — {t.fill_percentage}% full
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-gray-700">
              Reading Level (L)
            </label>
            <input
              required
              type="number"
              step="0.001"
              min="0"
              value={level}
              onChange={(e) => setLevel(e.target.value)}
              placeholder="e.g. 28500.000"
              className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-black/10"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-gray-700">Type</label>
              <select
                value={readingType}
                onChange={(e) => setReadingType(e.target.value)}
                className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-black/10"
              >
                <option value="manual">Manual Dip</option>
                <option value="automatic">Automatic Gauge</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-gray-700">
                Reading Time
              </label>
              <input
                type="datetime-local"
                value={readingAt}
                onChange={(e) => setReadingAt(e.target.value)}
                className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-black/10"
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-gray-700">
              Notes (optional)
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="Any observations…"
              className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-black/10 resize-none"
            />
          </div>
          {record.isError && (
            <p className="text-sm text-red-600">
              Failed to record dip. Please try again.
            </p>
          )}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 text-sm font-semibold text-gray-700 hover:bg-gray-50 transition-all"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={record.isPending}
              className="flex-1 px-4 py-2.5 rounded-xl bg-black text-white text-sm font-semibold hover:bg-zinc-800 transition-all disabled:opacity-50"
            >
              {record.isPending ? "Saving…" : "Record Dip"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Add Delivery Modal ────────────────────────────────────────────────────────

function AddDeliveryModal({ onClose }: { onClose: () => void }) {
  const { data: tankLevels } = useTankLevelsSummary();
  const tanks = tankLevels ?? [];
  const create = useCreateFuelDelivery();

  const [tankId, setTankId] = useState("");
  const [supplierId, setSupplierId] = useState("");
  const [deliveryDate, setDeliveryDate] = useState(
    new Date().toISOString().slice(0, 16),
  );
  const [volOrdered, setVolOrdered] = useState("");
  const [volReceived, setVolReceived] = useState("");
  const [unitCost, setUnitCost] = useState("");
  const [noteNumber, setNoteNumber] = useState("");
  const [notes, setNotes] = useState("");

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    await create.mutateAsync({
      tank_id: Number(tankId),
      supplier_id: Number(supplierId),
      delivery_date: new Date(deliveryDate).toISOString(),
      volume_ordered: volOrdered || undefined,
      volume_received: volReceived,
      unit_cost: unitCost,
      delivery_note_number: noteNumber || undefined,
      notes: notes || undefined,
    });
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-5 border-b border-gray-100 sticky top-0 bg-white rounded-t-2xl">
          <h3 className="text-lg font-bold text-gray-900">Add Fuel Delivery</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-gray-700">Tank</label>
            <select
              required
              value={tankId}
              onChange={(e) => setTankId(e.target.value)}
              className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-black/10"
            >
              <option value="">Select a tank…</option>
              {tanks.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} ({t.product_name})
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-gray-700">
              Supplier ID
            </label>
            <input
              required
              type="number"
              min="1"
              value={supplierId}
              onChange={(e) => setSupplierId(e.target.value)}
              placeholder="Enter supplier ID"
              className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-black/10"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-gray-700">
              Delivery Date &amp; Time
            </label>
            <input
              required
              type="datetime-local"
              value={deliveryDate}
              onChange={(e) => setDeliveryDate(e.target.value)}
              className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-black/10"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-gray-700">
                Volume Ordered (L)
              </label>
              <input
                type="number"
                step="0.001"
                min="0"
                value={volOrdered}
                onChange={(e) => setVolOrdered(e.target.value)}
                placeholder="Optional"
                className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-black/10"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-gray-700">
                Volume Received (L)
              </label>
              <input
                required
                type="number"
                step="0.001"
                min="0.001"
                value={volReceived}
                onChange={(e) => setVolReceived(e.target.value)}
                placeholder="e.g. 10000.000"
                className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-black/10"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-gray-700">
                Unit Cost (UGX/L)
              </label>
              <input
                required
                type="number"
                step="0.01"
                min="0.01"
                value={unitCost}
                onChange={(e) => setUnitCost(e.target.value)}
                placeholder="e.g. 4000.00"
                className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-black/10"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-gray-700">
                Delivery Note #
              </label>
              <input
                type="text"
                value={noteNumber}
                onChange={(e) => setNoteNumber(e.target.value)}
                placeholder="Optional"
                className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-black/10"
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-gray-700">
              Notes (optional)
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="Any delivery notes…"
              className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-black/10 resize-none"
            />
          </div>
          {volReceived && unitCost && (
            <div className="rounded-xl bg-gray-50 px-4 py-3 text-sm">
              <span className="text-gray-500">Estimated total cost: </span>
              <span className="font-bold text-gray-900">
                {fmtCost(
                  String(parseFloat(volReceived) * parseFloat(unitCost)),
                )}
              </span>
            </div>
          )}
          {create.isError && (
            <p className="text-sm text-red-600">
              Failed to record delivery. Please check the inputs and try again.
            </p>
          )}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 text-sm font-semibold text-gray-700 hover:bg-gray-50 transition-all"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={create.isPending}
              className="flex-1 px-4 py-2.5 rounded-xl bg-black text-white text-sm font-semibold hover:bg-zinc-800 transition-all disabled:opacity-50"
            >
              {create.isPending ? "Saving…" : "Record Delivery"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
