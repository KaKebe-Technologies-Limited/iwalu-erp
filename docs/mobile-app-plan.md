# Mobile App Plan — Nexus ERP Android (React Native)

**Project**: Nexus ERP — Kakebe Technologies  
**Document Type**: Technical Plan  
**Scope**: Android mobile app for fuel attendants and shop cashiers  
**Status**: Planning  
**Last Updated**: May 2026

---

## 1. App Overview

The Nexus ERP mobile app extends the ERP's POS capabilities to the field — fuel pump bays and shop tills — where a web browser is impractical. The app is Android-first, built in React Native, and designed to work reliably on low-end hardware with intermittent connectivity.

**Platform**: React Native (Android-first; iOS deferred)

**Target Devices**:
- Basic Android phones (Android 8.0+, 2 GB RAM minimum) — fuel pump attendants
- Sunmi P2 / PAX A920 smart Android POS terminals — shop tills
- Android tablets 8–10" — fixed till stations in café or supermarket

**Distribution**:
- Primary: Google Play Store (managed distribution via internal testing track, then production)
- Backup: USB side-load APK for provisioning in low-connectivity sites

**Scope — POS Only**:
The mobile app handles sales, shifts, and fuel tracking. Finance, HR, approvals, asset management, and system administration remain web-only. This is a deliberate scope boundary: the mobile app is a transaction capture tool, not a management console.

---

## 2. User Roles in Mobile App

Only two roles are supported in the mobile app. All other roles (admin, manager, accountant) use the web application.

### Attendant
Operates at the fuel pump bay. Tasks performed via mobile app:
- Open shift (assign pump, enter opening float)
- Record fuel sales per pump (UGX amount or litres)
- Accept payment (cash, MTN MoMo, Airtel Money)
- Print thermal receipt
- View current shift totals
- Close shift and submit reconciliation

### Cashier
Operates at a shop till (café, supermarket). Tasks performed via mobile app:
- Open shift (assign till, enter opening float)
- Scan or search for products (barcode or SKU/name)
- Add items to cart, adjust quantities
- Apply discounts (where eligible per role permissions)
- Accept split payments across multiple methods
- Print thermal receipt
- Close shift and submit reconciliation

Neither role can access product pricing admin, stock adjustments, user management, finance records, or any approval workflows from the mobile app.

---

## 3. Feature Scope (MVP)

### Authentication

- Login with email and password (same credentials as the web app, same backend JWT)
- On first login the app registers a device fingerprint server-side
- Biometric unlock after initial login (fingerprint/face) for speed at busy tills — no need to re-type credentials mid-shift
- PIN fallback (4–6 digits) if biometrics are unavailable or disabled
- **Offline continuity**: if the JWT access token expires during a shift, the app continues operating and queues a silent refresh. On reconnect, the token is refreshed before the next sync. If the account has been deactivated server-side, the shift is locked at next reconnect and a manager must intervene.

### Shift Management

- **Open shift**: select outlet, assign pump number (attendant) or till number (cashier), enter opening float amount
- **Current shift summary**: live count of transactions, total sales value, expected cash in drawer
- **Close shift**: triggers mandatory sync → reconciliation screen → manager confirmation → submit
- Shift cannot close while there are unsynced transactions or EFRIS queue items pending upload
- A shift is permanently bound to the user who opened it; another user cannot add transactions to someone else's open shift

### POS — Fuel Sales (Attendant)

- Select pump number from a list (pre-loaded at shift start)
- Enter sale amount in UGX or litres; app auto-converts using the current pump price loaded at shift start
- Price is read-only on device; server re-validates on sync
- Payment method: Cash, MTN MoMo, Airtel Money, Card (card is online-only; if offline, card payment is blocked)
- **MoMo payment flow**: enter customer phone number → app sends USSD push request to backend → status polling with 90-second timeout → confirm payment before issuing receipt
- Print receipt (thermal via built-in Sunmi/PAX printer or Bluetooth ESC/POS printer)
- Works fully offline for cash transactions; MoMo requires connectivity

### POS — Shop Sales (Cashier)

- Product search by name or SKU (searches local snapshot loaded at shift start)
- Camera barcode scanning using device camera — no external hardware required for phone-based tills
- External USB or Bluetooth barcode scanner supported via keyboard emulation mode (reads into the SKU field)
- Add product to cart, adjust quantity, remove line item
- Apply discount: percentage or fixed amount, subject to server-side eligibility rules validated at sync
- Split payment: assign amounts across multiple payment methods for one transaction
- Print receipt
- Works fully offline for cash; MoMo requires connectivity

### Inventory Quick View (Read-Only)

- Check current stock level for any product
- Low stock alerts surfaced as push notifications and in-app banners
- Stock adjustments, purchase orders, and transfers are web-only

### Notifications

- **Push notifications** (via Firebase Cloud Messaging): low stock threshold breached, approval request pending, sync failure alert
- **In-app notifications**: pending EFRIS items in queue, shift close reminder at end of configured hours, "last sync was X minutes ago" warnings

### Sync Status

- Persistent banner at top of screen showing count of transactions pending sync
- "Sync Now" button always accessible in the header
- Last successful sync timestamp displayed in Settings
- Sync runs automatically on reconnect (network state change listener)

---

## 4. Technical Architecture

### Technology Stack

| Layer | Choice | Reason |
|---|---|---|
| Framework | React Native (Expo bare workflow) | Code sharing with web where possible; large ecosystem |
| Local DB | WatermelonDB (SQLite via SQLCipher) | Offline-first, encrypted, reactive queries |
| UI state | Zustand | Lightweight, same pattern as web |
| API calls | TanStack Query | Consistent with web; handles caching and retry |
| Auth storage | react-native-keychain | Uses Android Keystore; never AsyncStorage |
| Printing | react-native-sunmi-printer / react-native-bluetooth-escpos-printer | Covers Sunmi built-in and external BT printers |
| Camera / Scan | react-native-vision-camera + barcode plugin | High-performance frame processor |
| Push | Firebase Cloud Messaging (FCM) | Standard Android push |
| Build / CI | GitHub Actions + Fastlane | Automated Play Store delivery |

### State Management

```
WatermelonDB (SQLite, encrypted)
  └── Persistent offline data (transactions, products snapshot, EFRIS queue)

Zustand (in-memory)
  └── Active shift state, cart contents, UI state, printer connection

TanStack Query (online)
  └── Authenticated API calls when connected (product sync, MoMo status poll)
```

### Offline Data Model

All tables live in a local SQLite database encrypted with SQLCipher.

```sql
-- Shifts table
shifts (
  id          TEXT PRIMARY KEY,   -- server-assigned ID (pre-created on open)
  outlet_id   INTEGER,
  user_id     INTEGER,
  opened_at   TEXT,               -- ISO 8601
  status      TEXT,               -- 'open' | 'pending_close' | 'closed'
  opening_float REAL
)

-- Transactions table
transactions (
  id              TEXT PRIMARY KEY,  -- UUID v4: device_id + timestamp + counter
  shift_id        TEXT,
  items_json      TEXT,              -- serialized line items
  total           REAL,
  payment_method  TEXT,
  sync_status     TEXT,             -- 'pending' | 'synced' | 'conflict'
  efris_status    TEXT,             -- 'pending' | 'queued' | 'submitted' | 'confirmed'
  created_at      TEXT,
  hmac_signature  TEXT              -- HMAC-SHA256 of payload, signed at creation
)

-- Product snapshot (loaded at shift start, read-only on device)
products (
  id       INTEGER PRIMARY KEY,
  name     TEXT,
  sku      TEXT,
  price    REAL,
  stock    REAL,
  synced_at TEXT
)

-- EFRIS offline queue
efris_queue (
  id             TEXT PRIMARY KEY,
  transaction_id TEXT,
  status         TEXT,   -- 'pending' | 'uploading' | 'confirmed' | 'failed'
  attempts       INTEGER DEFAULT 0,
  payload_json   TEXT,
  hmac_signature TEXT,   -- signed at creation, verified server-side before submission to URA
  created_at     TEXT,
  last_attempt_at TEXT
)

-- Receipts cache
receipts (
  id               TEXT PRIMARY KEY,
  transaction_id   TEXT,
  printed_at       TEXT,
  receipt_data_json TEXT
)
```

### Sync Engine

**Transaction ID generation**: `device_uuid + "-" + unix_ms + "-" + counter` produces a deterministic UUID v4. The server uses this as the idempotency key — re-submitting the same transaction ID is a no-op.

**Sync flow**:
1. App reconnects (network state event)
2. TanStack Query invalidates; sync job runs
3. App collects all transactions with `sync_status = 'pending'`
4. Batches up to 500 transactions per request
5. `POST /api/mobile/sync/` with HMAC-signed payload
6. Server responds: `{ confirmed: [...ids], conflicts: [...], efris_assigned: {...} }`
7. App updates local records: confirmed → `synced`, conflicts → flagged for manager review
8. EFRIS queue: confirmed URA numbers written back to local transaction records

**Conflict handling**: a conflict occurs when the server detects a price mismatch, an invalid discount, or a duplicate with different amounts. Conflicts are surfaced to the manager dashboard and do not block the shift from syncing other records.

### Receipt Printing

- **Sunmi/PAX built-in printer**: `react-native-sunmi-printer` (58mm thermal, ESC/POS)
- **Bluetooth printer**: `react-native-bluetooth-escpos-printer` (pair once, remembered per device)
- **Receipt format**: 58mm width, ESC/POS commands, includes: outlet name, date/time, cashier name, shift ID, line items, totals, payment method, EFRIS number (once confirmed), QR code for digital receipt
- **Fallback**: if no printer is paired, offer WhatsApp share or SMS of plain-text receipt summary

### Barcode Scanning

- `react-native-vision-camera` with `vision-camera-code-scanner` frame processor plugin
- Supports EAN-13, EAN-8, Code 128, QR codes
- External USB/Bluetooth scanner: keyboard emulation mode routes scan output directly into the active SKU text field — zero additional integration required
- Scanner activates when the POS screen's SKU field is focused

### Kiosk Mode

For fixed till installations on Sunmi/PAX terminals or dedicated Android tablets:
- Android `startLockTask()` API pins the Nexus ERP app to the foreground
- Home button, recent apps, and status bar are suppressed
- Manager PIN (entered on a separate PIN screen) exits kiosk mode
- Screen wake lock held during an open shift; screen dims (not off) after 2 minutes idle
- Kiosk mode is opt-in, configured per device in Settings by a manager

---

## 5. Screens List (MVP)

| Screen | Role | Notes |
|---|---|---|
| Login | All | Email + password; biometric after first login |
| Home | All | Shift status card, quick action buttons |
| Open Shift | All | Float entry, pump/till assignment |
| POS — Fuel Sale | Attendant | Pump select, UGX/litres entry, payment |
| POS — Shop Sale | Cashier | Cart with search/scan, qty adjustment |
| Payment Screen | All | Method selection, MoMo push flow, split payment |
| Receipt Preview + Print | All | Preview, print, share fallback |
| Shift Summary | All | Live totals, transaction list |
| Close Shift | All | Sync progress, reconciliation, submit |
| Inventory Quick Lookup | All | Search product, view stock level |
| Notifications | All | Push + in-app notification list |
| Settings | All | Printer pairing, sync status, biometric toggle, logout |
| Manager Exit PIN | Manager | Exits kiosk mode |

---

## 6. Backend API Requirements for Mobile

The following endpoints are required by the mobile app. Endpoints marked **New** need to be created. Endpoints marked **Existing** may need modification.

| Method | Endpoint | Status | Notes |
|---|---|---|---|
| `POST` | `/api/mobile/sync/` | **New** | Batch transaction upload; idempotent by transaction UUID; returns confirmed IDs, conflicts, EFRIS numbers |
| `GET` | `/api/mobile/shift-start-data/` | **New** | Returns product snapshot, current pump prices, outlet config, active discounts — all data needed to open a shift offline |
| `POST` | `/api/mobile/efris-queue/` | **New** | Flush offline EFRIS payloads; server verifies HMAC before forwarding to URA |
| `POST` | `/api/shifts/open/` | Existing | No changes required |
| `POST` | `/api/shifts/{id}/close/` | Existing — modify | Must validate: all transactions for shift are synced, EFRIS queue empty for shift; return 400 with reason if not |
| `GET` | `/api/products/` | Existing | Add `?outlet=X` filter if not already supported; ensure price field is included |
| `POST` | `/api/payments/momo/push/` | Existing | MoMo USSD push initiation; must return polling token |
| `GET` | `/api/payments/momo/status/{token}/` | Existing | MoMo payment status poll |
| `POST` | `/api/auth/token/refresh/` | Existing | Used silently on reconnect |
| `POST` | `/api/auth/device/register/` | **New** | Register device fingerprint on first login; associates device ID with user for audit logging |

**Mobile JWT Claim**: All mobile tokens must include `"client": "mobile"` in the payload. Admin and manager endpoints must reject tokens carrying this claim. This is a server-side enforcement — not a UI gate.

---

## 7. Development Phases

### Phase 1 — MVP Core (3 weeks)

Goal: An attendant can open a shift, record fuel sales offline, sync, and close a shift.

- React Native project setup (Expo bare), navigation structure, design tokens
- Authentication: login, JWT storage in Keystore, biometric unlock skeleton
- Shift open/close flows
- Fuel sale POS (UGX/litres entry, cash payment only)
- WatermelonDB + SQLCipher setup, offline transaction storage
- Basic sync engine (`POST /api/mobile/sync/`)
- Receipt printing via Sunmi built-in printer
- Sync status banner

**Milestone**: Attendant can operate a full shift with cash sales, offline, and sync cleanly.

### Phase 2 — Shop POS + Payments (4 weeks)

Goal: Cashier can run a full shop till including barcode scanning and mobile money.

- Shop POS: product search, cart, barcode scanning (vision-camera)
- Split payment UI
- MTN MoMo and Airtel Money push payment flow (online)
- EFRIS offline queue: create, sign, sync, flush
- Bluetooth printer support
- Low stock alerts (push notifications via FCM)
- Conflict resolution UI (flag mismatched transactions for manager)

**Milestone**: Cashier can handle a complete shop transaction with MoMo payment and EFRIS receipt.

### Phase 3 — Hardening + Distribution (2 weeks)

- Kiosk mode (Android `startLockTask()`)
- Full biometric login + PIN fallback
- Auto-wipe after 10 failed PIN attempts
- Certificate pinning
- Manager dashboard additions: per-device sync health, >60-minute no-sync alert
- Play Store internal testing track
- Fastlane + GitHub Actions CI/CD pipeline
- Play Store production release

**Milestone**: App live on Play Store, tested on Sunmi P2 and basic Android phone.

---

## 8. Play Store Deployment

**App ID**: `com.kakebetech.nexuserp`

**Target Android API**: 26+ (Android 8.0 Oreo minimum); target SDK 34

**Permissions**:
- `CAMERA` — barcode scanning
- `BLUETOOTH` / `BLUETOOTH_CONNECT` — Bluetooth printer pairing
- `INTERNET` — API sync
- `WAKE_LOCK` — keep screen active during open shift
- `VIBRATE` — payment confirmation feedback
- `USE_BIOMETRIC` / `USE_FINGERPRINT` — biometric unlock
- `RECEIVE_BOOT_COMPLETED` — restore kiosk mode after device restart

**Play Store Track Progression**:
1. Internal testing (team devices, Sunmi P2 terminal)
2. Closed testing (pilot fuel station)
3. Production release

**CI/CD Pipeline**:
- GitHub Actions triggers on `release/*` branch push
- Runs: lint → type-check → Jest tests → Detox E2E (optional, Phase 3)
- Fastlane `supply` uploads signed AAB to Play Store internal track
- Signing keystore stored as GitHub Actions encrypted secret

**Version Strategy**: SemVer `MAJOR.MINOR.PATCH`. Minor bumps for new features, patch for bug fixes. Play Store `versionCode` auto-incremented by CI.
