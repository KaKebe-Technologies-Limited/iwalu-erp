"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

// ── Mock data ───────────────────────────────────────────────────────────────

const roles = [
  { name: "Admin", users: 2, permissions: "Full access to all modules", color: "bg-red-50 text-red-700" },
  { name: "Manager", users: 3, permissions: "All modules except system settings", color: "bg-violet-50 text-violet-700" },
  { name: "Cashier", users: 8, permissions: "POS, view-only reports", color: "bg-blue-50 text-blue-700" },
  { name: "Pump Attendant", users: 16, permissions: "Fuel sales, shift reporting", color: "bg-emerald-50 text-emerald-700" },
  { name: "Accountant", users: 2, permissions: "Finance, payroll, reports", color: "bg-amber-50 text-amber-700" },
  { name: "Store Keeper", users: 3, permissions: "Inventory, stock management", color: "bg-gray-100 text-gray-700" },
];

const auditLogs = [
  { action: "User login", user: "Sarah Nakamya", ip: "192.168.1.42", time: "2 min ago", module: "Auth" },
  { action: "Created journal entry JE-1042", user: "David Ssali", ip: "192.168.1.45", time: "15 min ago", module: "Accounting" },
  { action: "Updated product price — Motor Oil 1L", user: "Moses Kato", ip: "192.168.1.38", time: "28 min ago", module: "Inventory" },
  { action: "Approved leave request — Florence Aber", user: "Sarah Nakamya", ip: "192.168.1.42", time: "1 hr ago", module: "HR" },
  { action: "Generated fuel reconciliation report", user: "System (Auto)", ip: "—", time: "2 hrs ago", module: "Reports" },
  { action: "New employee added — Rita Nambi", user: "Florence Aber", ip: "192.168.1.50", time: "3 hrs ago", module: "HR" },
];

// ── Component ───────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<"general" | "roles" | "notifications" | "system">("general");

  return (
    <div className="space-y-6 max-w-[1400px]">
      {/* Header */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight">
          Settings
        </h1>
        <p className="text-sm text-gray-500 mt-1">System configuration, roles, and preferences</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-xl overflow-x-auto">
        {([
          { id: "general", label: "General" },
          { id: "roles", label: "Users & Roles" },
          { id: "notifications", label: "Notifications" },
          { id: "system", label: "System" },
        ] as const).map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "px-4 py-2.5 rounded-lg text-sm font-semibold whitespace-nowrap transition-all",
              activeTab === tab.id ? "bg-white text-gray-900 shadow-sm" : "text-gray-500 hover:text-gray-700"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "general" && <GeneralSettings />}
      {activeTab === "roles" && <RolesSettings />}
      {activeTab === "notifications" && <NotificationSettings />}
      {activeTab === "system" && <SystemSettings />}
    </div>
  );
}

function GeneralSettings() {
  return (
    <div className="space-y-6">
      {/* Company Info */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-5">Company Information</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Company Name</label>
            <input type="text" defaultValue="Nexus Fuel Station Ltd" className="w-full px-4 py-2.5 rounded-xl border border-gray-200 text-sm focus:ring-2 focus:ring-black/5 focus:border-black outline-none transition-all" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">TIN Number</label>
            <input type="text" defaultValue="1000234567" className="w-full px-4 py-2.5 rounded-xl border border-gray-200 text-sm focus:ring-2 focus:ring-black/5 focus:border-black outline-none transition-all" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Email</label>
            <input type="email" defaultValue="info@nexusfuel.co.ug" className="w-full px-4 py-2.5 rounded-xl border border-gray-200 text-sm focus:ring-2 focus:ring-black/5 focus:border-black outline-none transition-all" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Phone</label>
            <input type="tel" defaultValue="+256 700 100 000" className="w-full px-4 py-2.5 rounded-xl border border-gray-200 text-sm focus:ring-2 focus:ring-black/5 focus:border-black outline-none transition-all" />
          </div>
          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Address</label>
            <input type="text" defaultValue="Plot 12, Olwol Road, Lira City, Uganda" className="w-full px-4 py-2.5 rounded-xl border border-gray-200 text-sm focus:ring-2 focus:ring-black/5 focus:border-black outline-none transition-all" />
          </div>
        </div>
        <div className="mt-6 flex justify-end">
          <button className="px-4 py-2.5 rounded-xl bg-black text-white text-sm font-semibold hover:bg-zinc-800 transition-all shadow-sm">
            Save Changes
          </button>
        </div>
      </div>

      {/* Business Settings */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-5">Business Settings</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Currency</label>
            <input type="text" defaultValue="UGX (Ugandan Shilling)" disabled className="w-full px-4 py-2.5 rounded-xl border border-gray-200 text-sm bg-gray-50 text-gray-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Timezone</label>
            <input type="text" defaultValue="Africa/Kampala (EAT, UTC+3)" disabled className="w-full px-4 py-2.5 rounded-xl border border-gray-200 text-sm bg-gray-50 text-gray-500" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Financial Year Start</label>
            <input type="text" defaultValue="January" className="w-full px-4 py-2.5 rounded-xl border border-gray-200 text-sm focus:ring-2 focus:ring-black/5 focus:border-black outline-none transition-all" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">VAT Rate</label>
            <input type="text" defaultValue="18%" className="w-full px-4 py-2.5 rounded-xl border border-gray-200 text-sm focus:ring-2 focus:ring-black/5 focus:border-black outline-none transition-all" />
          </div>
        </div>
      </div>

      {/* Receipt Settings */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-5">Receipt & Invoice</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Receipt Header</label>
            <input type="text" defaultValue="NEXUS FUEL STATION" className="w-full px-4 py-2.5 rounded-xl border border-gray-200 text-sm focus:ring-2 focus:ring-black/5 focus:border-black outline-none transition-all" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Receipt Footer</label>
            <input type="text" defaultValue="Thank you for your business!" className="w-full px-4 py-2.5 rounded-xl border border-gray-200 text-sm focus:ring-2 focus:ring-black/5 focus:border-black outline-none transition-all" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Print Format</label>
            <div className="flex gap-3">
              <label className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-gray-200 text-sm cursor-pointer hover:bg-gray-50 transition-all">
                <input type="radio" name="print" defaultChecked className="accent-black" />
                Thermal (80mm)
              </label>
              <label className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-gray-200 text-sm cursor-pointer hover:bg-gray-50 transition-all">
                <input type="radio" name="print" className="accent-black" />
                A4
              </label>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Show VAT on Receipt</label>
            <div className="flex gap-3">
              <label className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-gray-200 text-sm cursor-pointer hover:bg-gray-50 transition-all">
                <input type="radio" name="vat" defaultChecked className="accent-black" />
                Yes
              </label>
              <label className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-gray-200 text-sm cursor-pointer hover:bg-gray-50 transition-all">
                <input type="radio" name="vat" className="accent-black" />
                No
              </label>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function RolesSettings() {
  return (
    <div className="space-y-6">
      {/* Roles */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-bold text-gray-900">Roles & Permissions</h2>
          <button className="px-4 py-2.5 rounded-xl bg-black text-white text-sm font-semibold hover:bg-zinc-800 transition-all shadow-sm">
            + Add Role
          </button>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {roles.map((role) => (
            <div key={role.name} className="rounded-xl border border-gray-100 p-5 hover:shadow-md transition-all">
              <div className="flex items-center justify-between mb-3">
                <span className={cn("px-2.5 py-1 rounded-full text-xs font-semibold", role.color)}>
                  {role.name}
                </span>
                <span className="text-sm font-bold text-gray-900">{role.users} users</span>
              </div>
              <p className="text-xs text-gray-500">{role.permissions}</p>
              <button className="mt-3 text-xs font-semibold text-gray-500 hover:text-gray-900 transition-colors">
                Edit permissions →
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Audit Log */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-lg font-bold text-gray-900">Recent Activity Log</h2>
          <button className="text-sm font-semibold text-gray-500 hover:text-gray-900 transition-colors">View All</button>
        </div>
        <div className="divide-y divide-gray-50">
          {auditLogs.map((log, i) => (
            <div key={i} className="px-6 py-3.5 flex items-center justify-between hover:bg-gray-50/50 transition-colors">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-gray-50 flex items-center justify-center text-xs font-bold text-gray-600 flex-shrink-0">
                  {log.module.slice(0, 2).toUpperCase()}
                </div>
                <div>
                  <p className="text-sm font-semibold text-gray-900">{log.action}</p>
                  <p className="text-xs text-gray-400">{log.user} &middot; {log.ip}</p>
                </div>
              </div>
              <div className="text-right">
                <span className="px-2 py-1 rounded-md bg-gray-100 text-gray-600 text-xs font-medium">{log.module}</span>
                <p className="text-xs text-gray-400 mt-1">{log.time}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function NotificationSettings() {
  const notifications = [
    { name: "Low stock alerts", description: "When product falls below reorder level", email: true, inApp: true, sms: false },
    { name: "Daily sales summary", description: "End-of-day sales report", email: true, inApp: true, sms: false },
    { name: "Fuel variance alerts", description: "When variance exceeds tolerance", email: true, inApp: true, sms: true },
    { name: "Leave requests", description: "New leave request notifications", email: false, inApp: true, sms: false },
    { name: "Payroll reminders", description: "Upcoming payroll processing dates", email: true, inApp: true, sms: false },
    { name: "Tank level warnings", description: "Tank below 25% capacity", email: true, inApp: true, sms: true },
    { name: "System updates", description: "New features and maintenance", email: true, inApp: false, sms: false },
  ];

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-900">Notification Preferences</h2>
          <p className="text-sm text-gray-500 mt-1">Choose how you want to be notified</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50">
                <th className="text-left px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Notification</th>
                <th className="text-center px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">Email</th>
                <th className="text-center px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">In-App</th>
                <th className="text-center px-6 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wider">SMS</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {notifications.map((notif) => (
                <tr key={notif.name} className="hover:bg-gray-50/50 transition-colors">
                  <td className="px-6 py-4">
                    <p className="font-semibold text-gray-900">{notif.name}</p>
                    <p className="text-xs text-gray-400">{notif.description}</p>
                  </td>
                  <td className="px-6 py-4 text-center">
                    <input type="checkbox" defaultChecked={notif.email} className="w-4 h-4 accent-black rounded" />
                  </td>
                  <td className="px-6 py-4 text-center">
                    <input type="checkbox" defaultChecked={notif.inApp} className="w-4 h-4 accent-black rounded" />
                  </td>
                  <td className="px-6 py-4 text-center">
                    <input type="checkbox" defaultChecked={notif.sms} className="w-4 h-4 accent-black rounded" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="px-6 py-4 border-t border-gray-100 flex justify-end">
          <button className="px-4 py-2.5 rounded-xl bg-black text-white text-sm font-semibold hover:bg-zinc-800 transition-all shadow-sm">
            Save Preferences
          </button>
        </div>
      </div>
    </div>
  );
}

function SystemSettings() {
  return (
    <div className="space-y-6">
      {/* System Info */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-5">System Information</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: "Version", value: "1.0.0-beta" },
            { label: "Environment", value: "Development" },
            { label: "Database", value: "PostgreSQL 16" },
            { label: "Uptime", value: "99.9%" },
          ].map((info) => (
            <div key={info.label} className="rounded-xl bg-gray-50 p-4">
              <p className="text-xs text-gray-400 font-medium uppercase tracking-wider">{info.label}</p>
              <p className="text-lg font-bold text-gray-900 mt-1">{info.value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Approval Settings */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-5">Approval Thresholds</h2>
        <div className="space-y-4">
          {[
            { name: "Purchase Order Approval", threshold: "Above UGX 500K", approver: "Manager / Admin" },
            { name: "Leave Approval", threshold: "All requests", approver: "Station Manager" },
            { name: "Cash Requisition", threshold: "Above UGX 200K", approver: "Manager / Admin" },
            { name: "Price Change Approval", threshold: "All changes", approver: "Admin only" },
            { name: "Stock Adjustment", threshold: "Above 10 units", approver: "Manager / Admin" },
          ].map((approval) => (
            <div key={approval.name} className="flex items-center justify-between p-4 rounded-xl bg-gray-50 hover:bg-gray-100 transition-colors">
              <div>
                <p className="text-sm font-semibold text-gray-900">{approval.name}</p>
                <p className="text-xs text-gray-400">{approval.threshold}</p>
              </div>
              <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-violet-50 text-violet-700">
                {approval.approver}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Danger Zone */}
      <div className="bg-white rounded-2xl border border-red-200 shadow-sm p-6">
        <h2 className="text-lg font-bold text-red-600 mb-2">Danger Zone</h2>
        <p className="text-sm text-gray-500 mb-5">These actions are irreversible. Proceed with caution.</p>
        <div className="space-y-4">
          <div className="flex items-center justify-between p-4 rounded-xl bg-red-50/50">
            <div>
              <p className="text-sm font-semibold text-gray-900">Clear all cache</p>
              <p className="text-xs text-gray-400">Purge cached data and refresh from database</p>
            </div>
            <button className="px-4 py-2 rounded-xl border border-red-200 text-sm font-semibold text-red-600 hover:bg-red-50 transition-all">
              Clear Cache
            </button>
          </div>
          <div className="flex items-center justify-between p-4 rounded-xl bg-red-50/50">
            <div>
              <p className="text-sm font-semibold text-gray-900">Export all data</p>
              <p className="text-xs text-gray-400">Download complete database backup</p>
            </div>
            <button className="px-4 py-2 rounded-xl border border-red-200 text-sm font-semibold text-red-600 hover:bg-red-50 transition-all">
              Export Data
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
