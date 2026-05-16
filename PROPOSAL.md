# Comprehensive System Proposal {#comprehensive-system-proposal .unnumbered}

# Introduction

Nexus ERP is a fully integrated, cloud-based Enterprise Resource
Planning (ERP) system designed specifically for modern gas stations
operating multiple business units under one roof. These include fuel
services, café, bakery, supermarket, boutique, and bridal shop
operations. The system is built to unify all operational, financial, and
human resource processes into a single, secure, and scalable platform.
Nexus ERP is designed as a Software as a Service (SaaS) solution with
both online and offline capabilities, ensuring uninterrupted operations
even during internet outages. The system is fully responsive, dynamic,
and compatible with all devices including desktops, tablets, POS
terminals, and
smartphones.

# Objectives of the System

The primary objectives of Nexus ERP are to:

- Centralize management of all business units within the gas station
- Improve operational efficiency and accountability
- Automate finance, HR, inventory, and sales processes
- Enable real-time reporting and decision-making
- Support both online and offline operations with seamless data
  synchronization
- Provide a scalable SaaS platform for future growth

# System Overview

Nexus ERP is a multi-tenant SaaS platform, meaning it is hosted once on
the cloud and securely shared by multiple companies through subscription
access. Each company (tenant) has fully isolated data, configurations,
and users.
The system supports: - Multi-user access with role-based permissions -
Multi-branch and multi- department operations - Integrated POS across
all business units - Offline-first functionality with automatic
synchronization

# Core System Features

## User & Access Management

- Role-Based Access Control (RBAC) with 5-tier system (Admin, Manager,
  Accountant, Cashier, Attendant)
- Dynamic dashboard visibility based on fine-grained permissions
- Secure authentication and session management (JWT with social login support)
- Activity and audit logs for all system actions

## Approval Workflows

- Configurable multi-level approvals
- Department and amount-based approval rules (tenant-configurable)
- Applied to requisitions, payroll, purchases, and projects

## Notifications & Alerts

- Multi-channel notifications (In-app, email, and SMS)
- Templated messages for approvals, low stock, overdue advances, and
  system events

## System Configuration

- Tenant-level business rules and tax rates
- Approval thresholds and receipt formatting
- Customizable business rules per outlet or department

# Finance & Accounting Module

- Double-entry general ledger and chart of accounts
- Cash, bank, and mobile money account management
- Accounts payable and receivable
- Budget creation and enforcement
- Expense tracking
- Payroll processing with deductions and staff advances
- Financial statements (Profit & Loss, Balance Sheet, Trial Balance)
- Outlet-level and consolidated financial reporting
- Tax calculations and reporting

# Human Resources & Internal Operations

- Employee records and contracts
- Attendance and timesheets (Clock-in/out tracking)
- Leave management (annual, sick, maternity, unpaid) with balance tracking
- Cash requisitions and staff advances
- Approval workflows for HR requests
- Payroll generation and automated pay slips
- Asset assignment to staff
- HR analytics and reports

# POS, Sales, Invoicing & Receipts

- Multi-outlet POS system
- Support for fuel pumps, café, bakery, supermarket, boutique, and
  bridal shop
- Barcode and SKU-based sales
- Automatic stock deduction and low-stock indicators
- Discount and promotion management (Percentage and Fixed)
- Invoice and receipt generation
- Thermal and A4 printing support
- Multiple integrated payment methods: cash, bank, mobile money, card
- Daily cashier reconciliation and shift-based reporting

# Inventory & Store Management

- Comprehensive product and service catalog
- Multi-store and warehouse support
- Stock-in, stock-out, and inter-outlet transfers
- Reorder level alerts
- Supplier management and procurement tracking
- Purchase orders and deliveries
- Immutable stock audit logs and manual adjustments
- Perishable goods and expiry tracking
- Bundled product management

# Fuel Station Management

- Fuel sales tracking per pump and attendant
- Tank level and fuel inventory monitoring
- Daily fuel reconciliation and variance tracking
- Shift-based pump reporting
- Fuel delivery tracking and reconciliation with tanks

# Café & Bakery Management

- Menu and recipe management
- Ingredient-level stock deduction (Bill of Materials)
- Costing per item
- Dine-in and takeaway order management
- Promotions and combo offers
- Waste and expiry tracking

# Supermarket, Boutique & Bridal Shop Management

- Multi-category inventory management
- Barcode scanning for fast checkout
- Bundle and package sales (e.g., bridal packages)
- Outlet-specific stock and sales reports

# Project Management

- Project and task management
- Staff assignment
- Project budgets and expense tracking
- Time tracking
- Project profitability reports
- Approval workflows

# Subscription Billing

- Subscription plan creation
- Monthly and annual billing cycles
- Automatic invoice generation
- Payment tracking
- Revenue recognition and reporting

# Manufacturing & Bill of Materials (BOM)

- Raw material tracking
- Production orders
- Work-in-progress monitoring
- Finished goods inventory
- Costing per unit
- Automatic raw-to-finished stock conversion

# Asset Management

- Asset registration and categorization
- Assignment to departments or staff
- Maintenance and service logs
- Depreciation tracking
- Disposal records

# Mobile Money & Digital Payments

- Direct integration with MTN MoMo and Airtel Money APIs
- Integrated Collections (customer pays business via USSD push)
- Direct Disbursements (business pays customer/staff/supplier)
- Integrated Card Payments (Visa/Mastercard) via Pesapal
- Automatic reconciliation with POS and finance
- Secure transaction logs and callback/webhook auditing

# Tax Authority Integration (EFRIS)

- Direct EFRIS (URA) fiscalization for all sales
- Electronic receipting with mandatory FDN and QR codes
- Fiscal data integration with sales history and receipts
- Offline fiscalization queue with automatic background retry
- Export-ready tax reports and compliance logs

# Reporting & Analytics

- Role-based dashboards with real-time KPIs
- Sales and revenue reports per outlet and business unit
- Fuel performance analytics and variance reporting
- Inventory movement and stock aging
- HR and payroll reports
- Project and subscription performance
- Comprehensive system audit and activity logs

# Online & Offline Capability

Nexus ERP operates seamlessly both online and offline:

- Full POS and operational functionality when offline
- Local device storage for transactions
- Automatic background synchronization when internet returns
- Conflict detection and reconciliation
- Zero data loss and uninterrupted operations

# Responsiveness & Device Compatibility

- Fully responsive design
- Works on desktops, tablets, POS terminals, and smartphones
- Touch-friendly interfaces for POS and mobile devices
- Progressive Web App (PWA) support

# SaaS Architecture & Hosting

- Cloud-hosted SaaS platform
- Multi-tenant architecture with isolated PostgreSQL schemas
- Self-service tenant registration with automated email verification
  and provisioning
- Admin-initiated staff onboarding via email invitations (role-scoped,
  time-limited tokens)
- Role-based access control (RBAC) with dynamic dashboard gating per
  user role
- Secure data isolation per company
- Subscription-based access
- Automatic updates and backups
- Scalable infrastructure

# Benefits to the Client

- Single unified system for all operations
- Improved accountability and transparency
- Reduced operational errors and losses
- Real-time visibility into business performance
- Scalability for future growth
- Reduced IT and infrastructure costs

# Conclusion

Nexus ERP is a robust, future-ready enterprise management solution
designed to meet the complex needs of modern gas stations with multiple
business units. By combining finance, HR, inventory, POS, fuel
management, and analytics into one fully responsive and offline-capable
SaaS platform, Nexus ERP provides a reliable foundation for operational
excellence and sustainable growth.

> _End of Original Proposal_

---

# Operational & Technical Addendum

_Added May 2026 — documents architectural decisions made during implementation that extend or clarify the original proposal._

## Platform Strategy

The system is delivered across three platforms, each matched to its user:

| Platform | Target Users | Rationale |
|---|---|---|
| Web browser (responsive) | Admin, Manager, Accountant | Office-based; full desktop; no offline needed |
| Android native app (React Native) | Cashier, Attendant | Offline-first POS; receipt printing; Play Store distribution |
| PWA (supplement) | Tablets at shop tills | Secondary; read dashboards, not primary transaction entry |

**Why not PWA for POS**: Android OS aggressively kills browser service workers after inactivity. IndexedDB is cleared under memory pressure. For fuel transactions where receipts are legally required (EFRIS), PWA cannot guarantee transaction durability. The native app uses SQLite (WatermelonDB) with guaranteed ACID transactions and survives OS-level memory reclaim.

## Recommended Hardware

| Location | Device | Notes |
|---|---|---|
| Fuel pump attendant | Unlocked Android smart POS (e.g., Sunmi P2) or basic Android phone | Sunmi has built-in thermal printer; rugged; handheld |
| Shop till (café, supermarket) | Android tablet 8–10" + Bluetooth thermal printer (Epson TM-T82 or RP80) | Large screen for barcode scanning and cart |
| Manager / office | Laptop or desktop browser | No special hardware required |

**Important**: Bank-issued POS terminals (Ingenico, Verifone older models) run proprietary operating systems and cannot install custom apps — do not purchase these. Buy unlocked Android hardware from Sunmi, PAX, or generic Android tablet distributors.

**Kiosk mode**: Android devices at fuel pumps and shop tills should be locked to the Nexus ERP app using Android task pinning (kiosk mode) so attendants cannot browse other apps during a shift. A manager PIN is required to exit kiosk mode.

**App distribution**: The Android app is published to Google Play Store. Side-loading via USB is supported for provisioning without internet.

## Offline Operation & Sync

### Shift-Locked Offline Model
All offline activity is scoped to a shift. The app operates offline by default and syncs to the server opportunistically. Sync is triggered:
- Silently, on any reconnect during a shift (to minimise data loss window)
- Mandatorily, at shift close — shift cannot be closed until all transactions are confirmed synced and the EFRIS queue is empty

### Conflict Resolution Rules
- **Product prices changed while offline**: server re-validates totals on sync; manager is notified of any discrepancies; sale is not auto-voided.
- **Duplicate transaction**: server detects duplicate UUID and rejects second; client marks as `sync_failed`; manager alerted.
- **Shift force-closed on server while attendant offline**: sync rejected; flagged for manual reconciliation.
- **Account deactivated while offline**: transactions sync for audit trail; session invalidated on reconnect.

### Sync Latency SLA
- Manager dashboard reflects all synced transactions within 60 seconds of attendant reconnecting.
- A device with no sync activity for more than 60 minutes triggers a manager alert.

### EFRIS Offline Queue
Offline sales are queued locally with a pending status. On any network reconnect, the queue is flushed to URA's EFRIS API. Receipts printed offline display "PENDING TAX REGISTRATION" until the fiscal document number (FDN) is confirmed. Shift close is blocked until the EFRIS queue is empty.

## Staff Onboarding

1. Business owner registers on the platform (self-service tenant signup).
2. Admin invites staff via email (role-scoped, time-limited invitation token).
3. Staff member clicks link, sets password, and is provisioned to the tenant with their assigned role.
4. Admin assigns staff member to an outlet.
5. Staff member downloads the Android app from Google Play Store (for field roles) or accesses the web dashboard (for office roles).

## Security Notes

- All offline transactions are signed with an HMAC at creation time. Server verifies signature on sync — tampered payloads are rejected.
- Local SQLite database on mobile is encrypted with SQLCipher (key derived from user PIN + device hardware ID).
- JWT tokens are stored in Android Keystore (not plain storage). Biometric unlock is supported.
- No card numbers are stored locally — card payments are online-only.
- Customer phone numbers captured for mobile money are purged from local storage immediately after sync is confirmed.

See `docs/ARCHITECTURE.md`, `docs/offline-first.md`, and `docs/security-audit-offline.md` for full technical detail.
