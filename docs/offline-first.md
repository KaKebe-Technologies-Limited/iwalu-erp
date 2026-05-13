# Offline-First Architecture — Nexus ERP Mobile

**Applies to**: React Native mobile app (cashier and attendant roles)  
**Does NOT apply to**: Next.js web app (admin, manager, accountant — online only)  
**Last Updated**: May 2026

---

## Table of Contents

1. [Philosophy](#1-philosophy)
2. [Local Storage Strategy](#2-local-storage-strategy)
3. [Sync Protocol](#3-sync-protocol)
4. [Conflict Detection and Resolution](#4-conflict-detection-and-resolution)
5. [EFRIS Offline Queue](#5-efris-offline-queue)
6. [Kiosk Mode Setup](#6-kiosk-mode-setup)
7. [Receipt Printing](#7-receipt-printing)
8. [Failure Scenarios and Recovery](#8-failure-scenarios-and-recovery)
9. [Data Schema Reference](#9-data-schema-reference)
10. [Testing Offline Behavior](#10-testing-offline-behavior)

---

## 1. Philosophy

### Core Principles

**Offline-first**: The mobile app assumes no internet is available. Every feature that a cashier or attendant needs during a shift must work with zero connectivity. Network access is treated as a bonus, not a requirement.

**Shift-locked**: All offline data is scoped to a shift. A shift is the fundamental unit of work. Every transaction, every EFRIS queue entry, every receipt belongs to exactly one shift. This scoping simplifies conflict resolution and gives a natural sync boundary.

**Manual sync**: Synchronization with the server is user-triggered at shift close, not a continuous background process. This is intentional. Background sync on Android is unreliable — the OS kills background processes after periods of inactivity. Making sync explicit gives the cashier a clear moment of confirmation: "Your data is synced. Your shift is closed."

**Zero data loss**: The local database (WatermelonDB / SQLite) is the source of truth during a shift. A transaction is not considered complete until it is written to SQLite — the network call is secondary. SQLite's ACID properties guarantee that a transaction is either fully written or fully rolled back, even under power loss.

**Guaranteed durability before receipt**: The sequence is always: write to SQLite → print receipt. Never print a receipt for a transaction that has not been durably committed to local storage.

### Why Not a PWA?

Progressive Web Apps were evaluated and rejected for operational staff. The key reasons:

- Android OS kills service workers after 10–30 minutes of inactivity to conserve battery. A cashier who steps away during a quiet period can return to a dead service worker — any in-progress state is lost.
- Browser-based IndexedDB has per-origin storage quotas (~50–100 MB on most Android devices). A busy shift with receipt images and EFRIS payloads can saturate this quota.
- Browser APIs for Bluetooth printer access (Web Bluetooth) are experimental and unreliable on the Android WebView environment used by budget phones.
- SQLite (via WatermelonDB) provides full ACID guarantees. IndexedDB's behavior under power loss is browser-vendor-dependent.

PWA is available as a supplementary access method for managers checking data on a phone, but it is not used for operational (transactional) workflows.

---

## 2. Local Storage Strategy

### Technology

**WatermelonDB** running on top of SQLite via `react-native-sqlite-storage`.

WatermelonDB was chosen over plain SQLite, AsyncStorage, or Realm for the following reasons:

| Criterion | WatermelonDB | Plain SQLite | AsyncStorage | Realm |
|-----------|-------------|-------------|-------------|-------|
| ACID transactions | Yes | Yes | No | Yes |
| Lazy loading (perf) | Yes | Manual | N/A | Yes |
| Sync protocol built-in | Yes (optional) | No | No | Partial |
| React Native integration | First-class | Bridge required | Native | Bridge required |
| License | MIT | Public domain | MIT | Apache 2 |
| Encryption (SQLCipher) | Yes | Yes | No | Commercial |

The database file is encrypted using SQLCipher. The encryption key is derived from a combination of the device hardware ID and a per-device key issued by the server at first login. See [Security Architecture](ARCHITECTURE.md#5-security-architecture) for details.

### What Is Stored Offline

#### Products Catalog (read-only during shift)

Synced from server at shift start. Treated as immutable for the duration of the shift — price changes on the server do not affect an in-progress shift.

```
products
  id              TEXT  (server UUID)
  name            TEXT
  sku             TEXT
  price           TEXT  (stored as string to avoid float precision issues)
  category        TEXT
  stock_quantity  INTEGER
  unit            TEXT
  snapshot_shift  TEXT  (shift_id this snapshot belongs to)
  synced_at       TEXT  (ISO 8601)
```

#### Current Shift Metadata

```
shifts
  id              TEXT  (server-assigned shift ID)
  cashier_id      INTEGER
  cashier_name    TEXT
  outlet_id       INTEGER
  outlet_name     TEXT
  opened_at       TEXT
  status          TEXT  (open | syncing | closed)
  opening_cash    TEXT
  declared_cash   TEXT  (set at close time)
```

#### Transactions

```
transactions
  id              TEXT  (deterministic UUID: device_id + shift_id + counter, see §3)
  shift_id        TEXT
  sale_type       TEXT  (fuel | shop | cafe)
  subtotal        TEXT
  discount_amount TEXT
  tax_amount      TEXT
  total           TEXT
  created_at      TEXT
  sync_status     TEXT  (pending | uploading | synced | sync_failed | sync_conflict)
  server_id       INTEGER  (null until synced)
```

#### Transaction Line Items

```
transaction_items
  id              TEXT
  transaction_id  TEXT  (FK → transactions.id)
  product_id      TEXT
  product_name    TEXT  (snapshot at time of sale)
  quantity        TEXT
  unit_price      TEXT  (snapshot at time of sale)
  total           TEXT
```

#### Transaction Payments

```
transaction_payments
  id              TEXT
  transaction_id  TEXT  (FK → transactions.id)
  method          TEXT  (cash | mtn_momo | airtel_money | card | credit)
  amount          TEXT
  reference       TEXT  (MoMo reference number, card auth code, etc.)
```

#### EFRIS Queue

```
efris_queue
  id              TEXT
  transaction_id  TEXT  (FK → transactions.id)
  shift_id        TEXT
  payload_json    TEXT  (full EFRIS request payload, serialized)
  status          TEXT  (pending | uploading | confirmed | failed | escalated)
  fdn_placeholder TEXT  (locally generated placeholder FDN for offline receipts)
  fdn_confirmed   TEXT  (official FDN from URA, set on confirmation)
  retry_count     INTEGER (default 0)
  last_error      TEXT
  created_at      TEXT
  confirmed_at    TEXT
```

#### Receipt Cache

Last 50 receipts stored as JSON blobs, TTL of 24 hours. Used for re-printing without hitting the server.

```
receipt_cache
  id              TEXT
  transaction_id  TEXT
  receipt_json    TEXT
  printed_at      TEXT
  expires_at      TEXT
```

### What Is NOT Stored Offline

The following data categories are never cached locally on the device:

- **Historical reports**: Sales summaries, trend reports, financial statements. These require online access.
- **Other users' data**: The app only holds data for the currently logged-in cashier's active shift.
- **Finance and accounting entries**: Journal entries, chart of accounts, payroll. These are back-office operations only available via the web app.
- **HR records**: Employee profiles, leave balances, attendance history.
- **Other tenants' data**: Strictly never. The device is bound to one tenant at provisioning time.
- **Full product history**: Only the current shift's catalog snapshot is stored. Previous snapshots are purged after shift close sync.

---

## 3. Sync Protocol

### Transaction ID Generation

Every local transaction is assigned a **deterministic UUID** before any network call is made:

```
transaction_id = SHA1( device_id + ":" + shift_id + ":" + local_counter )
```

Where:
- `device_id`: A UUID generated once at app first launch and stored in encrypted AsyncStorage. Stable for the lifetime of the app install.
- `shift_id`: The server-assigned shift ID received when the shift was opened.
- `local_counter`: An integer incremented atomically for each transaction within the shift. Stored in WatermelonDB.

This scheme guarantees:
1. IDs are unique per device per shift.
2. IDs are stable — the same transaction always gets the same ID even if the app crashes and restarts.
3. The server can detect duplicates (if the same ID is POSTed twice, it rejects the second).
4. IDs are not sequential integers — they do not expose business volume to anyone who intercepts them.

### Step-by-Step Sync Flow

#### Step 0: App Launch

```
App opens
    │
    ├── Check network connectivity (NetInfo)
    │
    ├── If ONLINE:
    │   ├── GET /api/auth/refresh/ (silent token refresh)
    │   ├── GET /api/products/?active=true (product catalog)
    │   └── Sync any pending EFRIS entries from a previous session
    │
    └── If OFFLINE:
        └── Load last-known product catalog from local DB
            (display "Offline mode — using cached catalog" badge in UI)
```

#### Step 1: Shift Start

```
Cashier taps "Start Shift"
    │
    ├── ONLINE: POST /api/shifts/open/ → receive shift_id
    │               │
    │               └── GET /api/products/?snapshot=true → store in local DB
    │                   (locked as read-only for this shift)
    │
    └── OFFLINE: Cannot open shift (server must assign shift_id)
                 Display: "You need internet to start a shift."
                 (This is the only hard online requirement in the cashier flow)
```

Starting a shift requires connectivity. This is an intentional constraint: the server assigns the canonical `shift_id` that anchors all offline data. Without it, deterministic UUIDs cannot be generated correctly.

#### Step 2: Transaction (Online or Offline)

```
Cashier completes a sale
    │
    ├── Generate deterministic transaction_id
    ├── WatermelonDB.write():
    │   ├── INSERT transactions (status: pending)
    │   ├── INSERT transaction_items (× line items)
    │   ├── INSERT transaction_payments (× payment methods)
    │   └── INSERT efris_queue (status: pending)
    │
    ├── Print receipt immediately (from local data, PENDING FISCALIZATION if offline)
    │
    └── Return cashier to POS screen (< 200ms total, no network call)

    [ Async, non-blocking ]
    ├── If ONLINE: attempt immediate EFRIS upload and transaction sync
    └── If OFFLINE: transactions stay in pending state until sync
```

#### Step 3: Mid-Shift Opportunistic Sync

```
Network connectivity detected (NetInfo event)
    │
    ├── Collect all transactions with status: pending
    ├── POST /api/shifts/{shift_id}/sync-transactions/
    │   (batch of 50 per request)
    │
    ├── On success: UPDATE transactions SET status = 'synced', server_id = <id>
    │
    └── Collect all EFRIS entries with status: pending
        ├── POST each to URA EFRIS API
        └── On success: UPDATE efris_queue SET status = 'confirmed', fdn_confirmed = <fdn>
```

This step runs silently in the background and does not block or interrupt the cashier's UI. It is fire-and-forget — if it fails, it will be retried at shift close.

#### Step 4: Shift Close (Mandatory Full Sync)

```
Cashier taps "Close Shift"
    │
    ▼
Pre-flight check:
    ├── Count pending transactions → N
    ├── Count pending EFRIS entries → M
    └── Show: "Closing shift — syncing N transactions and M fiscal receipts..."

PHASE A: Transaction Sync
    ├── Must be ONLINE (block if offline, show "Connect to internet to close shift")
    ├── POST /api/shifts/{shift_id}/sync-transactions/ (all remaining pending)
    ├── Server returns: { accepted: [ids], rejected: [ids], conflicts: [ids] }
    ├── rejected → mark sync_failed, surface to manager
    ├── conflicts → mark sync_conflict, surface to manager
    └── Loop in batches until all pending transactions processed

PHASE B: EFRIS Flush
    ├── POST each pending EFRIS entry to URA API (sequentially, in order)
    ├── On success: status = confirmed
    ├── On failure: retry × 3 (exponential backoff: 2s, 4s, 8s)
    ├── After 3 failures: status = escalated, alert manager
    └── Block shift close until: all entries are confirmed OR escalated
        (escalated entries do not block close — manager resolves separately)

PHASE C: Shift Close API Call
    ├── POST /api/shifts/{shift_id}/close/ { declared_cash, pump_readings }
    ├── Server validates: no pending sync records exist for this shift
    ├── Server calculates: expected_total vs declared_total (variance report)
    └── Returns: { shift_summary, variance_report, efris_summary }

PHASE D: Post-Close
    ├── Display shift summary to cashier
    ├── Offer: "Re-print receipts with fiscal numbers" (for any PENDING receipts now confirmed)
    ├── Purge local DB: delete shift transactions, items, payments, EFRIS entries, receipt cache
    └── Return to "Start New Shift" screen
```

---

## 4. Conflict Detection and Resolution

### Duplicate Transaction ID

**Scenario**: The same transaction is POSTed to the server twice (e.g., the first POST succeeded but the app did not receive the 201 response and retried).

**Server behavior**: The server's sync endpoint is idempotent on `transaction_id`. If the same ID is received:
- First occurrence: accepted, stored, `server_id` assigned.
- Second occurrence: HTTP 200 returned with the existing `server_id`. Not treated as an error.

**Client behavior**: The client stores the returned `server_id` for both attempts. No duplicate records created.

**Edge case — genuine duplicate**: If two devices somehow generate the same `transaction_id` (should be mathematically impossible given the device_id + shift_id + counter scheme, but defensive programming is warranted):
- Server detects: same `transaction_id`, different `device_id` in payload.
- Server rejects second with HTTP 409.
- Client marks transaction `sync_conflict`, surfaces to manager dashboard.
- Manager reviews and resolves manually.

### Price Drift

**Scenario**: A product's price was updated on the server while the attendant was mid-shift offline.

**Rule**: Server wins for pricing. The catalog snapshot taken at shift start is for display and receipt generation only. On sync, the server recalculates line totals using the authoritative price at the time the sale was recorded.

**Process**:
1. Server compares submitted `unit_price` per line item against `products_product.price` at `transaction.created_at`.
2. If difference exists: server stores the submitted price in `sale_item.offline_unit_price`, stores the recalculated total in `sale_item.total`, and flags the transaction `price_adjusted = True`.
3. Manager receives a notification: "5 transactions from Shift #42 had prices adjusted on sync. Review required."
4. The sale is NOT voided. It remains in the record. The manager decides whether any follow-up action (e.g., issuing a refund) is warranted.

### Shift Force-Closed on Server

**Scenario**: A manager closes the shift remotely from the web dashboard while the attendant's device is offline.

**Server behavior**: The shift's `status` is set to `force_closed` on the server.

**Client behavior on sync attempt**:
1. Server returns HTTP 409 with `reason: SHIFT_FORCE_CLOSED`.
2. App enters "emergency sync" mode.
3. All pending transactions are uploaded to an `orphaned_transactions` queue (separate from normal sync).
4. EFRIS queue is flushed.
5. App displays to attendant: "Your shift was closed by your manager. Your transactions have been saved for review."
6. Manager sees orphaned transactions in the dashboard and manually reconciles.

### Deactivated Account

**Scenario**: A user account is deactivated on the server while the attendant is mid-shift offline.

**Process**:
1. On any network reconnect, silent token refresh fails (HTTP 401, user inactive).
2. App sets `session_invalid = true` locally.
3. Current in-progress transaction (if any) is allowed to complete. Do not interrupt a payment mid-flow.
4. After the current transaction completes, the app displays: "Your account has been deactivated. Contact your manager."
5. Shift close is attempted — sync of existing transactions proceeds (for audit), but session is terminated after sync completes.
6. App returns to login screen and clears all session state.

---

## 5. EFRIS Offline Queue

### Background

Uganda Revenue Authority mandates EFRIS (Electronic Fiscal Receipting and Invoicing Solution) fiscal receipts for all taxable sales. The EFRIS API is a web service provided by URA. It is online-only — there is no offline mode provided by URA.

Nexus ERP's offline EFRIS queue bridges this gap by:
1. Recording all required fiscal data locally at point of sale.
2. Uploading to URA's API as soon as connectivity is available.
3. Printing interim receipts with a "PENDING FISCALIZATION" watermark.
4. Re-issuing or updating receipts once URA confirms the FDN.

### Queue Entry Lifecycle

```
Sale completed (offline)
    │
    ▼
efris_queue entry created
    ├── status: pending
    ├── fdn_placeholder: "PENDING-{device_id}-{counter}" (locally generated)
    └── payload_json: full EFRIS request (taxpayer PIN, items, totals, tax breakdown)
    │
    ▼
Receipt printed with fdn_placeholder + "PENDING FISCALIZATION" watermark
    │
    ▼
Network available?
    │
    YES ──► POST to URA EFRIS API endpoint
    │               │
    │          Success ──► status: confirmed, fdn_confirmed: <URA FDN>
    │               │
    │          HTTP 4xx (invalid data) ──► status: failed, retry_count++
    │               │                      log error, alert if retry_count > 3
    │          HTTP 5xx / timeout ──► retry with backoff (2s, 4s, 8s)
    │
    NO ──► Entry remains: pending
           (will be uploaded at next connectivity event or shift close)
    │
    ▼
Shift close: EFRIS flush required before close is permitted
    │
    ▼
All entries confirmed (or escalated after 3 failures)
    │
    ▼
Cashier offered: "Re-print receipts with fiscal numbers"
```

### Retry Policy

| Retry Count | Action |
|-------------|--------|
| 0–2 | Automatic retry with exponential backoff |
| 3 | Status set to `escalated`; manager alerted |
| Escalated | Manager can: retry manually, enter FDN from URA portal manually, flag for compliance review |

### Preventing Data Loss

EFRIS queue entries must not be lost. Three safeguards:

1. **Upload on any reconnect**: The app listens for NetInfo connectivity events. On any transition from offline to online — even briefly mid-shift — pending EFRIS entries are uploaded immediately. This reduces the number of entries that need to be flushed at shift close.

2. **Server heartbeat at shift start**: When the shift is opened, the app registers the `device_id` and `shift_id` on the server. If the server does not receive a shift close for that shift after 24 hours, it flags the shift as `abandoned` and alerts the tenant admin. This creates a signal that there may be unsynced data on a device.

3. **ACID writes**: EFRIS queue entries are written in the same WatermelonDB transaction as the sale. If the app crashes immediately after writing the sale but before printing the receipt, the EFRIS entry still exists in the DB and will be uploaded at next launch.

### Receipt Update After Fiscalization

When an EFRIS entry transitions from `pending` to `confirmed`:

1. The `fdn_confirmed` is stored in both the `efris_queue` record and the corresponding transaction record.
2. The receipt cache is updated with the confirmed FDN.
3. The cashier is notified (in-app badge): "X receipts have been fiscalized and can be re-printed."
4. On request, the app re-prints the receipt with:
   - The official URA FDN prominently displayed.
   - A QR code linking to the URA receipt verification portal.
   - The "PENDING FISCALIZATION" watermark removed.

---

## 6. Kiosk Mode Setup

Devices issued to attendants and cashiers are locked to the Nexus ERP app using Android's task pinning (kiosk mode). This prevents attendants from browsing social media, using messaging apps, or accessing device settings during a shift.

### Setup Procedure (Per Device)

**One-time device provisioning** (done by IT admin before device is issued):

1. **Factory reset** the device and complete the Android setup wizard.
2. **Disable auto-sleep** during shifts:
   - Settings → Display → Screen timeout → Set to "Never" or maximum.
3. **Install Nexus ERP** from Google Play Store (or side-load APK).
4. **Enable kiosk mode** via the app's admin setup screen:
   - Launch the app.
   - On the login screen, enter the **device provisioning code** (generated in the Nexus admin dashboard for this tenant).
   - The app will:
     a. Register the device with the server.
     b. Receive a per-device encryption key (stored in encrypted AsyncStorage).
     c. Enable Android task pinning programmatically.
     d. Prompt for a **manager exit PIN** (4–8 digits). Set this now.
5. **Verify kiosk mode**: Press the Android home button. The device should not navigate away from the app.

### Kiosk Behavior During a Shift

- The Android navigation bar (home, back, recents) is hidden or non-functional.
- Physical hardware buttons (volume, power) function normally (attendants need to adjust volume and screen brightness).
- Attendants cannot access Settings, other apps, or the notification shade.
- Incoming calls: the app shows a "Call incoming" overlay (the attendant can answer/decline) but the call does not exit kiosk mode.
- Screen stays on during shift (wake lock held by the app).

### Exiting Kiosk Mode

Only a manager can exit kiosk mode:

1. Long-press the Nexus ERP logo in the top-left corner for 3 seconds.
2. Enter the manager PIN.
3. Android kiosk mode is released.
4. The device returns to normal Android operation.

This is needed for: OS updates, app updates, device troubleshooting.

### MDM Alternative

For larger deployments (10+ devices), consider a Mobile Device Management solution:

- **Google Workspace for Business** includes Android Enterprise with managed kiosk profiles.
- This allows remote device management, remote kiosk lock/unlock, and forced app updates without physical access.
- Configuration: Enroll devices in Android Enterprise, push a kiosk profile that whitelists only the Nexus ERP app.

For small deployments (1–5 devices), the built-in app-level kiosk mode described above is sufficient.

---

## 7. Receipt Printing

### Supported Hardware

| Device Type | Printer | Library | Notes |
|-------------|---------|---------|-------|
| Sunmi P2 / P2 Lite | Built-in thermal printer | `react-native-sunmi-printer` | 58mm, direct SDK call, fastest |
| PAX A920 / A930 | Built-in thermal printer | `react-native-pax-printer` | Similar to Sunmi |
| Android tablet / phone | Epson TM-T82 (Bluetooth) | `react-native-bluetooth-escpos-printer` | Pair device once, persistent |
| Android tablet / phone | RP80 (Bluetooth) | `react-native-bluetooth-escpos-printer` | Budget option |

All printers use 58mm thermal paper rolls (the most widely available size in Uganda, available at most stationery shops).

### Receipt Layout (58mm)

```
================================
        NEXUS ERP
   [Tenant Business Name]
   [Outlet Name, Address]
   TIN: [Taxpayer PIN]
================================
Receipt #: [transaction_id_short]
Date: 2026-05-08  Time: 14:32
Cashier: [cashier_name]
Shift: [shift_id_short]
--------------------------------
ITEM           QTY  PRICE  TOTAL
Petrol (L)     20   5,800  116,000
Coffee          1   3,500    3,500
--------------------------------
SUBTOTAL              119,500
Discount (5%)          -5,975
TAX (18% VAT)          20,331
TOTAL                 133,856
================================
PAYMENT
Cash                  150,000
Change                 16,144
================================
EFRIS FDN: [fdn]
[QR code to URA verification]
================================
  Thank you for your business!
================================
```

**Offline receipt** (before EFRIS confirmation):

```
================================
  ** PENDING FISCALIZATION **
  This receipt will be re-issued
  with a fiscal number once
  connectivity is restored.
  Placeholder: [fdn_placeholder]
================================
```

### Bluetooth Printer Pairing

1. Power on the Bluetooth printer.
2. In the Nexus ERP app: Settings → Printer Setup → Scan for Bluetooth printers.
3. Select the printer from the list. Pair using PIN (usually `0000` or `1234`).
4. The app stores the printer's MAC address. It reconnects automatically on subsequent app launches.
5. If the printer is not found: verify it is powered on, in range (< 10m), and not paired to another device.

### Print Flow

```javascript
// Pseudocode — actual implementation uses WatermelonDB queries + printer SDK

async function printReceipt(transactionId: string): Promise<void> {
  // 1. Load transaction from local DB
  const transaction = await db.transactions.find(transactionId);
  const items = await transaction.items.fetch();
  const payments = await transaction.payments.fetch();
  const efrisEntry = await transaction.efrisQueue.fetch();

  // 2. Build receipt data
  const receipt = buildReceiptData(transaction, items, payments, efrisEntry);

  // 3. Print via appropriate SDK
  if (isSunmiDevice()) {
    await SunmiPrinter.printReceipt(receipt);
  } else {
    await BluetoothPrinter.printReceipt(receipt, storedPrinterMac);
  }

  // 4. Update receipt cache
  await db.receiptCache.create({ transactionId, receiptJson: JSON.stringify(receipt) });
}
```

### Re-Printing After EFRIS Confirmation

When an EFRIS entry is confirmed and a `fdn_confirmed` is received:

1. Load the receipt from cache (or rebuild from local DB).
2. Replace `fdn_placeholder` with `fdn_confirmed`.
3. Remove the "PENDING FISCALIZATION" watermark.
4. Add the URA QR code (link: `https://efris.ura.go.ug/verify/{fdn_confirmed}`).
5. Print.

---

## 8. Failure Scenarios and Recovery

### Scenario 1: Device Battery Dies Mid-Shift

**What happens**:
The device powers off unexpectedly. Any in-progress screen state is lost.

**Recovery**:
1. Charge the device and restart.
2. The Nexus ERP app launches and detects the existing open shift in local WatermelonDB.
3. The app resumes the shift automatically — the cashier is returned to the POS screen.
4. All transactions written before the power loss are intact (SQLite persists to flash storage, ACID-compliant).
5. Any transaction that was in the process of being written to SQLite at the exact moment of power loss is rolled back (ACID guarantee). That transaction was never printed, so there is no orphaned receipt.
6. Mid-shift EFRIS and sync proceeds normally.

**Cashier sees**: "Resuming your shift. X transactions recorded."

---

### Scenario 2: Internet Never Returns During the Entire Shift

**What happens**:
The device is offline for the full shift. All transactions are in local DB. No mid-shift sync occurs.

**Recovery**:
1. At shift close, the cashier must go to a location with internet connectivity (e.g., the manager's office, a router).
2. The app connects and performs the mandatory sync (Phases A–D in §3, Step 4).
3. If internet is genuinely not available for an extended period (e.g., ISP outage): the shift remains open.
4. The manager can flag the shift as "extended offline" in the dashboard, which pauses any auto-escalation timers.
5. Once connectivity returns (even hours or days later), the cashier syncs and closes the shift.

**Constraint**: Shifts cannot be closed without connectivity. This is intentional — it enforces that all data reaches the server before the cashier's liability for the shift is released.

---

### Scenario 3: App Crashes Mid-Transaction

**What happens**:
The app process is killed by the OS or crashes due to a bug while a transaction is being processed.

**Recovery**:
- If the crash occurred **before** the WatermelonDB write completed: the transaction was never committed (ACID rollback). Nothing is lost. The cashier restarts the sale from scratch. No orphaned receipt was printed (print happens after write).
- If the crash occurred **after** the WatermelonDB write but **before** the receipt was printed: the transaction is in the DB. On app restart, the app detects the unprinted transaction and offers: "The app closed during a transaction. Print the receipt now?"
- If the crash occurred **after** the receipt was printed: the transaction is fully recorded. Shift continues normally.

**Cashier sees** on restart: The POS screen, possibly with a "print pending receipt" prompt.

---

### Scenario 4: Device Lost or Stolen

**What happens**:
The device goes missing during a shift. It may contain unsynced transactions.

**Immediate actions** (manager):
1. In the Nexus admin dashboard: navigate to Devices → [device] → Revoke Device Key.
2. This invalidates the per-device encryption key on the server.
3. Even if the device is found and powered on, the local SQLite DB cannot be decrypted — the encryption key is gone.
4. In the Shifts dashboard: the shift is shown as open, last sync at `[time]`.
5. Manager manually force-closes the shift, marks it as `device_lost`.
6. Any transactions synced before the device was lost are in the server DB and are valid.
7. Unsynced transactions are logged as `irrecoverable` in the shift reconciliation record.

**Audit trail**: The shift record notes: "Shift force-closed due to device loss at [time]. [N] transactions synced. [M] transactions unrecoverable. Physical cash count performed at [time] by [manager]."

**EFRIS**: Any unsynced EFRIS entries on the lost device are irrecoverable. The manager must manually account for these in the compliance log, noting the device loss. URA's field compliance guidance accepts device loss as a documented exception.

---

### Scenario 5: Sync Fails Partway Through

**What happens**:
The mandatory sync at shift close starts, uploads 30 of 50 transactions, then internet drops.

**Recovery**:
1. The app detects the connectivity loss and pauses the sync.
2. Displays: "Sync paused — lost internet connection. Waiting to resume..."
3. When connectivity returns (even if it takes 30 minutes), sync resumes from where it left off.
4. Already-uploaded transactions are not re-uploaded (the server is idempotent on `transaction_id`; already-accepted IDs are simply acknowledged again).
5. The shift does not close until all transactions and EFRIS entries are processed.

---

### Scenario 6: EFRIS API Returns Persistent Errors

**What happens**:
URA's EFRIS API is returning HTTP 500 or is unreachable for an extended period (URA server maintenance).

**Recovery**:
1. After 3 failed retry attempts per entry, status is set to `escalated`.
2. Escalated entries do NOT block shift close.
3. Manager is alerted: "X EFRIS entries failed to fiscalize. Manual intervention required."
4. Manager options in dashboard:
   - **Retry now**: Attempt upload again (useful if URA outage has cleared).
   - **Manual FDN**: Enter the FDN from the URA web portal directly (for cases where the receipt was fiscalized through an alternate channel).
   - **Flag for compliance**: Mark as escalated-unavoidable, add a note for the compliance record.
5. URA guidance: if the EFRIS system is unavailable, businesses are expected to document the outage and fiscalize the receipts as soon as the system is restored.

---

## 9. Data Schema Reference

The complete WatermelonDB schema is defined in `mobile/src/database/schema.ts`. Key constraints:

- All monetary values are stored as `TEXT` (string representation of integers in the smallest currency unit, e.g., UGX shillings). This prevents floating-point precision errors.
- All timestamps are stored as ISO 8601 strings in UTC.
- Foreign keys within WatermelonDB are `text` fields (WatermelonDB uses string IDs, not integers).
- Server IDs (when received after sync) are stored as separate `INTEGER` fields alongside the local string ID.

---

## 10. Testing Offline Behavior

### Development Testing

Enable airplane mode on the Android emulator or physical device:

```bash
# Emulator: disable network via adb
adb shell svc wifi disable
adb shell svc data disable

# Re-enable
adb shell svc wifi enable
adb shell svc data enable
```

Use the Reactotron debugger to inspect WatermelonDB state during offline testing.

### Automated Tests

Write integration tests that explicitly control the network mock:

```typescript
// Example using jest + mock for NetInfo
jest.mock('@react-native-community/netinfo', () => ({
  addEventListener: jest.fn(),
  fetch: jest.fn(() => Promise.resolve({ isConnected: false })),
}));

test('transaction is saved locally when offline', async () => {
  // Mock offline state
  NetInfo.fetch.mockResolvedValue({ isConnected: false });

  // Process a sale
  await processTransaction(mockSaleData);

  // Verify WatermelonDB record created
  const transactions = await db.collections.get('transactions').query().fetch();
  expect(transactions).toHaveLength(1);
  expect(transactions[0].syncStatus).toBe('pending');

  // Verify no network call was made
  expect(global.fetch).not.toHaveBeenCalled();
});
```

### Shift Close Sync Testing Checklist

Before releasing a new version, manually verify:

- [ ] 50+ offline transactions sync correctly at shift close
- [ ] Duplicate transaction ID is handled gracefully (no duplicate in DB)
- [ ] EFRIS queue flushes completely before shift close is permitted
- [ ] Shift close is blocked when offline (correct error message)
- [ ] Battery kill mid-transaction recovers correctly on restart
- [ ] Price-adjusted transactions are flagged in manager dashboard
- [ ] Bluetooth printer reconnects after app restart
- [ ] Kiosk mode prevents home button navigation
- [ ] Manager PIN exits kiosk mode correctly
- [ ] Device key revocation locks local DB
