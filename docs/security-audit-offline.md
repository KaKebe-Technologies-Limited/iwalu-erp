# Security Audit — Offline Transaction Handling

**Project**: Nexus ERP — Kakebe Technologies  
**Document Type**: Security Audit  
**Scope**: Mobile app offline POS transactions, local storage, sync protocol, EFRIS queue, session management  
**Status**: Pre-implementation review  
**Last Updated**: May 2026  
**Classification**: Internal — Engineering + Management

---

## 1. Audit Scope

This audit covers the offline transaction handling design for the Nexus ERP Android mobile app (React Native). It is a pre-implementation review, written before code is committed to production, to identify risks early so mitigations can be built in rather than bolted on.

**In scope**:
- Mobile app offline POS transaction recording (fuel sales, shop sales)
- Local SQLite database storage on the device
- Sync protocol: device to backend (`POST /api/mobile/sync/`)
- EFRIS offline queue: creation, signing, upload, URA submission
- Session and authentication management during offline periods
- Device loss and theft scenarios

**Out of scope**:
- Web application security (covered separately)
- Backend infrastructure security (AWS/server hardening)
- Payment gateway security (MTN MoMo, Airtel — governed by their provider SDKs)
- Physical security of POS terminals (site management responsibility)

**Assumptions**:
- The backend runs over HTTPS (TLS 1.3)
- Devices are company-provisioned or employee-owned (BYOD with MDM policy)
- Sunmi/PAX POS terminals run a locked-down Android ROM from the manufacturer

---

## 2. Risk Register

Risks are scored by **Severity** (impact if exploited) and **Likelihood** (probability of occurring without controls).

---

### RISK-01: Local SQLite Data Theft

**Severity**: HIGH  
**Likelihood**: MEDIUM (device loss is common in field environments)

**Description**: The local SQLite database contains daily transaction records, customer phone numbers (collected for MoMo payments), shift float amounts, and product pricing snapshots. On a standard Android installation, SQLite databases in the app's data directory are accessible to root users, ADB-connected workstations, and to anyone who obtains a full device backup. A lost or stolen attendant phone without encryption allows an attacker to extract the database file and read all records with standard SQLite tooling.

**Data exposed if exploited**:
- Daily sales totals and per-transaction breakdown
- Customer mobile numbers (MoMo payment records)
- Opening float amounts (reveals cash-handling patterns)
- Product pricing and stock snapshot

**Mitigation**:
1. Encrypt the SQLite database with SQLCipher. This is a compile-time replacement for SQLite that applies AES-256 encryption to the entire database file transparently.
2. Derive the encryption key from the user's PIN (4–6 digit minimum) combined with the device's hardware ID (Android `ANDROID_ID` or attestation certificate). Neither the PIN nor the hardware ID alone is sufficient to open the database.
3. Use PBKDF2 with SHA-256, 100,000 iterations to derive the key from the PIN. This makes brute-forcing the PIN against the encrypted DB computationally expensive.
4. The derived key is held only in process memory during an active session. It is never written to disk.
5. Auto-lock the app after 5 minutes of inactivity; the key is zeroed from memory on lock. Re-unlock requires biometric or PIN.
6. Enable Android's full-disk encryption requirement (`android:allowBackup="false"` in manifest, `usesCleartextTraffic="false"` in network security config).

---

### RISK-02: Transaction Replay Attack

**Severity**: CRITICAL  
**Likelihood**: LOW (requires network interception or server-side access, but impact is severe)

**Description**: An attacker who captures a sync payload (via MITM, rogue API endpoint, or insider access) could re-submit it to the server. If the server processes it again, this creates duplicate transaction records, potentially crediting revenue that was not earned or inflating sales figures. In a fuel station context, duplicate fuel dispensing records could mask theft or create false audit trails.

**Mitigation**:
1. **Deterministic UUID per transaction**: each transaction ID is generated as `device_uuid + unix_timestamp_ms + per-session-counter`. The same transaction will always produce the same ID. The server stores all confirmed transaction IDs and rejects any submission with a duplicate ID (HTTP 409, silently discarded from the UI).
2. **HMAC signature on each transaction**: at the moment a transaction is recorded locally, the app computes `HMAC-SHA256(transaction_payload, device_secret_key)`. The device secret key is generated on first registration and stored in Android Keystore (hardware-backed on supported devices). The server verifies the HMAC before accepting each transaction. A replayed payload with a tampered amount will fail HMAC verification.
3. **HMAC signature on the sync batch**: the entire sync request payload is also HMAC-signed. The server rejects any batch with an invalid envelope signature before processing individual records.
4. **Timestamp binding**: each transaction includes a `created_at` timestamp. The server rejects transactions with `created_at` older than the maximum offline window (48 hours). This limits the replay window.

---

### RISK-03: Offline Price Manipulation

**Severity**: HIGH  
**Likelihood**: MEDIUM (insider threat; technically possible on a rooted device)

**Description**: The product catalog and pricing snapshot is stored in the local SQLite database so the POS can operate offline. An attacker with root access to the device (or a rogue employee who roots their phone) could directly edit the SQLite database to reduce product prices before recording sales. Transactions with manipulated prices would sync to the server and, if accepted, would create false low-price sales records that undercount revenue.

**Mitigation**:
1. **SQLCipher encryption** (RISK-01) prevents direct SQLite manipulation without the decryption key, raising the bar significantly.
2. **Server-side price re-validation on sync**: the sync endpoint does not trust prices submitted by the device. For each transaction, the server looks up the canonical price for the product at the time of the transaction (using the `created_at` timestamp and the product price history). If the submitted price deviates by more than a configurable tolerance (e.g., 0%), the transaction is flagged as a conflict.
3. **Conflict review queue**: price-conflict transactions are not rejected outright (to avoid blocking legitimate edge cases) but are placed in a manager review queue. The manager sees the submitted price vs. the expected price and must approve or reject.
4. **Audit log**: every sync event records which device submitted which transactions, allowing forensic analysis if a pattern of price manipulation is detected.
5. **Discount eligibility enforced server-side**: discount applicability is re-validated on sync. A discount that was not eligible at transaction time is rejected regardless of what the device submitted.

---

### RISK-04: Expired Session Abuse

**Severity**: MEDIUM  
**Likelihood**: LOW (requires physical access to an unlocked device)

**Description**: JWT access tokens expire after 1 hour. During a long offline period (e.g., a full 8-hour shift with no connectivity), the token will expire. The app continues operating with the expired token cached locally. If the device is lost or left unlocked during this period, an attacker could open the app and record transactions under the authenticated user's identity without needing to re-authenticate.

**Mitigation**:
1. **Kiosk mode** (Android `startLockTask()`) on fixed till devices prevents any navigation away from the app.
2. **Biometric or PIN required to unlock**: after 5 minutes of inactivity the app locks. Resuming requires biometric (fingerprint/face) or PIN. This is enforced at the app level regardless of device lock screen state.
3. **Shift-bound session**: transactions are tied to the open shift. The shift is tied to the authenticated user. A new session opening (someone else logging in) requires the previous shift to be closed first. An abandoned unlocked device can only be used to add transactions to the current authenticated user's shift — it cannot create a new session or access another user's data.
4. **Manager force-close**: a manager can remotely force-close an abandoned shift via the web dashboard. This freezes the shift and prevents new transactions from being added.

---

### RISK-05: EFRIS Queue Tampering

**Severity**: HIGH  
**Likelihood**: LOW (requires rooted device + knowledge of data format)

**Description**: Uganda Revenue Authority's EFRIS fiscalization requires that a signed receipt be issued for every taxable sale. If EFRIS payloads queued in the local database are tampered with before upload — changing amounts, omitting line items, or altering tax codes — the URA receives incorrect fiscal data. This constitutes tax evasion and could expose Kakebe Technologies and its clients to criminal liability under Uganda's tax laws.

**Mitigation**:
1. **HMAC signature at creation**: when an EFRIS queue entry is created (immediately after a transaction is recorded), the app computes `HMAC-SHA256(efris_payload_json, device_secret_key)` and stores the signature alongside the payload.
2. **Immutable after signing**: the EFRIS payload and its signature are written to the local DB in the same transaction. The application code has no update path for EFRIS payloads — only inserts and status updates (which do not touch the payload or signature fields).
3. **Server verifies before URA submission**: the sync endpoint verifies the HMAC of each EFRIS entry before forwarding it to URA. Any entry with an invalid signature is rejected, logged, and escalated to a compliance alert.
4. **URA response binding**: the URA-assigned invoice number returned after successful submission is written back to the local transaction record. Any discrepancy between the local transaction and the URA record is detectable during audit.

---

### RISK-06: Man-in-the-Middle Attack During Sync

**Severity**: HIGH  
**Likelihood**: LOW (requires network-level access; higher risk on shared WiFi at petrol stations)

**Description**: When the device reconnects and begins syncing, an attacker on the same network could intercept the sync payload. This could expose transaction data (customer phone numbers, sales amounts) or, if the attacker can modify the payload in transit, inject fraudulent transactions or suppress legitimate ones. Petrol station environments often use shared WiFi with limited network segmentation.

**Mitigation**:
1. **HTTPS only — no HTTP fallback**: the app's network security config (`network_security_config.xml`) explicitly prohibits cleartext traffic. Any attempt to connect over HTTP results in a connection error, not a downgrade.
2. **TLS 1.3 minimum**: backend NGINX/server configured to reject TLS 1.2 and below. The React Native HTTP client is configured with the same minimum.
3. **Certificate pinning**: the app pins the Kakebe Technologies server's leaf certificate (or intermediate CA public key hash). Any certificate not matching the pin — including forged certificates from a rogue CA — causes the connection to be refused. Implemented via `react-native-ssl-pinning` or OkHttp's `CertificatePinner` via the native module layer.
4. **Pin rotation plan**: certificate pinning creates a risk of app breakage if the server certificate changes. Pins must be updated in the app before the server certificate expires. A 6-month rotation schedule with a backup pin in the app at all times mitigates this.
5. **HMAC-signed payloads** (RISK-02): even if an attacker intercepts and replays a payload, the HMAC prevents undetected modification.

---

### RISK-07: Device Shared Between Multiple Attendants

**Severity**: MEDIUM  
**Likelihood**: HIGH (common in low-staffing environments; one phone used per pump bay, not per person)

**Description**: In practice, devices may be shared between shift workers — an attendant hands the phone to the next shift without closing the first shift. Transactions from the second attendant would be recorded under the first attendant's open shift, incorrectly attributing sales and distorting per-employee performance and accountability records.

**Mitigation**:
1. **Shift is user-bound**: a shift cannot be opened while another user's shift is already open on the same device. The app shows a prominent "Shift open by [Name] since [Time]" warning screen on launch.
2. **Cannot record transactions under someone else's open shift**: the POS screens are blocked if the logged-in user does not match the shift owner. A different attendant must either: (a) ask the first attendant to close their shift, or (b) request a manager force-close.
3. **Manager force-close**: available via web dashboard. Force-closes the shift, marks it as "force-closed by manager", and flags it for reconciliation review.
4. **Shift hand-over procedure**: documented in operator training. The app guides the outgoing attendant through the close-shift flow before handing the device over.

---

### RISK-08: Sync Flood / Denial of Service

**Severity**: MEDIUM  
**Likelihood**: LOW (requires authenticated device; more likely accidental than malicious)

**Description**: A malfunctioning app, a bug in the sync engine, or a malicious actor with a stolen device could submit thousands of transactions to the sync endpoint in rapid succession. This could overload the database, exhaust storage, or trigger excessive EFRIS API calls to URA (which has rate limits).

**Mitigation**:
1. **Rate limiting on sync endpoint**: limit to N sync requests per device per minute (e.g., 10 requests/minute). Excess requests receive HTTP 429.
2. **Batch size cap**: maximum 500 transactions per sync request. Larger batches are rejected with HTTP 400.
3. **Valid shift ID required**: the server validates that the `shift_id` referenced in the sync payload exists in the server database and is in `open` status. Transactions referencing a non-existent or closed shift are rejected.
4. **Device-level audit log**: every sync request is logged with device ID, user ID, transaction count, and timestamp. Anomalous patterns (e.g., 10,000 transactions from one device in one hour) trigger an automated alert to the tenant admin.
5. **EFRIS rate limit buffer**: EFRIS submissions from the backend to URA are queued via a background worker with rate limiting. A sync flood will fill the queue but will not directly overwhelm the URA API.

---

### RISK-09: Data Loss on Device Destruction

**Severity**: HIGH  
**Likelihood**: MEDIUM (device battery death, screen break, or theft mid-shift)

**Description**: If a device is destroyed or stolen during a shift before transactions are synced, those sales records are permanently lost. This has two serious consequences: (1) the business cannot reconcile cash collected with system records, and (2) unsynced EFRIS queue entries mean those sales were never fiscalized — a regulatory non-compliance issue under Uganda's EFRIS mandate.

**Mitigation**:
1. **Mid-shift sync (not only at close)**: the sync engine runs automatically on any network reconnect event, not only when the shift is being closed. Transactions are uploaded as they are created whenever connectivity is available. This reduces the unsynced window to the duration of the most recent offline period.
2. **Manager dashboard sync health**: the manager web dashboard shows per-device sync status: last sync timestamp, count of pending transactions, and time since last sync.
3. **Alert at 60-minute no-sync**: if a device has an open shift with unsynced transactions and has not successfully synced in 60 minutes, a push notification is sent to the manager and the attending employee (if their phone number is on file).
4. **Receipt as secondary record**: a printed thermal receipt is generated for every transaction at the point of sale. Even if the device is destroyed, the printed receipt provides a basis for manual data recovery.
5. **EFRIS queue persistence across app restart**: the EFRIS queue survives app crashes and device reboots (it is persisted in the encrypted SQLite DB). On next launch, the queue resumes uploading automatically.

---

### RISK-10: Privilege Escalation via Mobile API

**Severity**: CRITICAL  
**Likelihood**: MEDIUM (without explicit controls, mobile JWT tokens are indistinguishable from web tokens)

**Description**: The mobile app authenticates with the same backend as the web application and receives a standard JWT. Without additional controls, a sophisticated attacker could extract the JWT from a device (via ADB, a rooted phone, or a backup exploit) and use it to call admin or manager endpoints — listing all users, adjusting stock, modifying prices, or accessing financial records — from a browser or curl.

**Mitigation**:
1. **Mobile JWT claim**: all tokens issued via the mobile login flow include a custom claim: `"client": "mobile"`. This claim is set by the backend when the login request includes the device fingerprint header (`X-Device-ID`).
2. **Admin/manager endpoint rejection of mobile tokens**: a middleware/permission class on the backend inspects the JWT `client` claim. Endpoints classified as admin or manager-only reject any request bearing `"client": "mobile"` with HTTP 403, regardless of the user's role.
3. **Mobile-specific API routes**: endpoints designed for mobile use (e.g., `/api/mobile/sync/`) require `"client": "mobile"`. Web-only endpoints require `"client": "web"` or absence of the mobile claim. This creates a clean boundary.
4. **JWT stored in Android Keystore**: the access and refresh tokens are stored using `react-native-keychain`, which uses the Android Keystore hardware-backed secure enclave on supported devices. Extraction via ADB or backup requires the device to be unlocked and the app to expose the key, neither of which is straightforward.
5. **Scope reduction**: mobile JWTs are issued with a minimal scope claim covering only the operations the mobile app legitimately performs (shift management, transaction recording, product lookup). Backend enforces scope on each request.

---

## 3. Authentication Security

### JWT Token Storage
- Tokens (access + refresh) stored exclusively via `react-native-keychain`
- On Android: uses Keystore-backed encrypted shared preferences (hardware-backed on Android 9+ devices with Titan M or equivalent chip)
- `AsyncStorage` is explicitly prohibited for any credential or token storage — it is unencrypted plain text
- Refresh token rotation: each refresh produces a new refresh token; old token is invalidated server-side

### Biometric Authentication
- Implemented via `react-native-biometrics` (Android BiometricPrompt API)
- Biometric data never leaves the device; the OS returns only a cryptographic success/failure signal
- Biometric is used to unlock the app session (decrypt the PIN from Keystore, which in turn provides the SQLCipher key) — it is not used to directly authenticate against the backend
- Cannot be bypassed remotely; requires physical presence on the device

### Offline Token Validity
- During an active shift, the app accepts an expired access token for local operations
- On reconnect, the app silently posts the refresh token to `/api/auth/token/refresh/`
- If the refresh fails (account deactivated, refresh token revoked), the app transitions to a "shift locked" state: no new transactions can be recorded; existing unsynced transactions are preserved; the screen shows "Session expired — contact manager"
- A manager can unlock via a management override code entered on the device

### PIN Security
- PIN is 4–6 digits minimum (6 recommended; configurable by tenant admin)
- PIN is never stored; it is used transiently to derive the SQLCipher key via PBKDF2
- 10 consecutive failed PIN attempts triggers auto-wipe (see Section 4)
- PIN change requires the current PIN to be known (cannot reset PIN without the current PIN + manager intervention)

---

## 4. Data at Rest

### SQLite Encryption
- Database encrypted with SQLCipher (AES-256-CBC)
- Key derivation: `PBKDF2(HMAC-SHA256, user_pin, device_hardware_id, 100_000_iterations, 32_bytes)`
- `device_hardware_id` sourced from Android attestation where available; fallback to `ANDROID_ID`
- The derived key is passed directly to SQLCipher's `PRAGMA key` at database open; it is never written to any file or persisted in any form

### Auto-Wipe
- After 10 consecutive failed PIN attempts, the app deletes the local SQLite database file and clears all Keystore entries
- This is irreversible: any unsynced transactions are permanently lost (see RISK-09 mitigations)
- Wipe event is logged to a remote audit endpoint if network is available at time of wipe

### Receipt Cache
- Receipt data (including customer-visible totals, line items, and EFRIS number) is stored in the `receipts` table, which is part of the same encrypted SQLCipher database
- Receipts are purged after confirmed sync + 7 days (configurable)

### Customer Phone Numbers (MoMo)
- Mobile money phone numbers are stored only in the `transactions` table as part of `items_json`
- Purge policy: after sync is confirmed by the server, the phone number field in the local record is overwritten with a null value — the server holds the canonical record
- This minimizes the personal data held locally to the minimum necessary window

---

## 5. Data in Transit

### Transport Layer
- TLS 1.3 minimum; TLS 1.2 and below rejected at the server
- The Android network security configuration (`res/xml/network_security_config.xml`) disables cleartext traffic globally for the app:

```xml
<network-security-config>
    <base-config cleartextTrafficPermitted="false">
        <trust-anchors>
            <certificates src="system" />
        </trust-anchors>
    </base-config>
    <domain-config>
        <domain includeSubdomains="true">api.nexuserp.kakebetech.com</domain>
        <pin-set expiration="2027-05-01">
            <pin digest="SHA-256">PRIMARY_CERT_PIN_BASE64==</pin>
            <pin digest="SHA-256">BACKUP_CERT_PIN_BASE64==</pin>
        </pin-set>
    </domain-config>
</network-security-config>
```

### Certificate Pinning
- Both a primary pin and a backup pin are included at all times
- When a certificate renewal is planned, the new certificate's public key hash is added as the backup pin at least 30 days before the old certificate expires
- After the old certificate expires, the app release removes the old pin
- Pinning failure causes a hard error with user-visible message ("Connection security check failed — contact support")

### HSTS
- Backend server sets `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- Once a device has connected successfully, the HSTS policy is cached by the HTTP client

---

## 6. Audit Logging

The following events are logged server-side with full context (user ID, device ID, tenant ID, IP address, timestamp):

| Event | Fields Logged |
|---|---|
| Sync request received | device_id, user_id, transaction_count, shift_id, timestamp, source_ip |
| Sync accepted | confirmed_ids count, conflict_ids count |
| Sync rejected | reason (invalid HMAC, expired shift, rate limit, etc.) |
| EFRIS upload attempt | efris_entry_ids, attempt_count, ura_response_code |
| EFRIS upload success | ura_invoice_number, submission_timestamp |
| EFRIS signature mismatch | entry_id, device_id, alert_generated=true |
| Device registered | device_id, user_id, platform, android_api_level |
| Auto-wipe triggered | device_id, user_id (if known), timestamp, network_available |
| Session locked (offline) | device_id, shift_id, reason |
| Manager force-close | shift_id, target_user_id, manager_user_id |
| Price conflict detected | transaction_id, submitted_price, expected_price, product_id |

Audit logs are write-only from the application perspective (append-only table, no update/delete permissions for the application database user). Log retention: minimum 7 years (Uganda tax compliance).

### Manager Dashboard Visibility
- Per-device sync health panel: last sync time, pending transaction count, shift status
- Alert feed: devices with no sync >60 minutes, EFRIS signature failures, auto-wipe events, price conflicts
- Per-shift audit trail: all transactions, their sync timestamps, EFRIS status, any conflicts

---

## 7. Compliance Notes

### EFRIS (Uganda Revenue Authority)
- All offline sales must be fiscalized. The EFRIS queue must be fully uploaded before a shift can be closed.
- The app enforces this at the UI level: the "Close Shift" button is disabled while `efris_queue` contains entries with `status != 'confirmed'`.
- The backend enforces this at the API level: `POST /api/shifts/{id}/close/` returns HTTP 400 if the shift's EFRIS queue is not empty.
- Failure to fiscalize within the shift window must trigger an escalation alert to the tenant admin (not silently ignored).

### Data Protection (Uganda Data Protection and Privacy Act 2019)
- Customer mobile numbers collected for MoMo payments are personal data under the Act.
- They are collected for the sole purpose of processing the payment transaction.
- Local retention is minimized: purged from the local DB after server sync is confirmed.
- Server-side retention follows the tenant's configured data retention policy.
- No customer phone numbers are logged in server-side audit logs (they appear only in the encrypted transaction payload).

### PCI-DSS (Card Payments)
- Card payments are online-only. If the device is offline, card payment is blocked at the UI level.
- No card numbers, CVVs, or card track data are ever stored locally. The local database schema has no fields for card data.
- Card transactions are processed via the payment gateway's SDK, which manages its own PCI-compliant tokenization.

---

## 8. Recommendations Summary

The following actions are required before the mobile app can be submitted to the Play Store or deployed to any production site. They are listed in priority order.

| Priority | Ref | Action | Owner |
|---|---|---|---|
| CRITICAL | RISK-01 | Implement SQLCipher encryption for the local WatermelonDB/SQLite database. Without this, all offline data is readable on a stolen device. | Mobile dev |
| CRITICAL | RISK-02, RISK-05 | Add HMAC-SHA256 signing to all transaction records and all EFRIS queue entries at the point of creation. Implement server-side HMAC verification before accepting any sync payload. | Mobile dev + Backend dev |
| CRITICAL | RISK-06 | Implement certificate pinning in the React Native app via `network_security_config.xml`. Define a pin rotation procedure and schedule. | Mobile dev + DevOps |
| HIGH | RISK-01 | Implement auto-wipe after 10 consecutive failed PIN attempts. Ensure the wipe event is reported to the audit log before executing. | Mobile dev |
| HIGH | RISK-10 | Add `"client": "mobile"` claim to mobile JWTs. Enforce rejection of mobile-claim tokens on all admin/manager backend endpoints via middleware. | Backend dev |
| HIGH | RISK-09 | Implement mid-shift sync (trigger on every network reconnect, not only at shift close). Validate that this reduces the unsynced data window in offline field testing. | Mobile dev |
| HIGH | RISK-03 | Implement server-side price re-validation on sync. Build the conflict review queue in the manager dashboard. | Backend dev + Frontend dev |
| MEDIUM | RISK-09 | Implement manager alert when a device with an open shift has not synced for >60 minutes. Add per-device sync health panel to manager dashboard. | Backend dev + Frontend dev |
| MEDIUM | RISK-08 | Apply rate limiting to `POST /api/mobile/sync/`: max 10 requests per device per minute, max 500 transactions per batch. | Backend dev |
| MEDIUM | RISK-07 | Document and test the shift hand-over procedure. Ensure the "Shift open by [Name]" warning screen is prominent and cannot be bypassed by the next user. | Mobile dev |

---

*This document should be reviewed and updated each time the mobile sync protocol or local data model changes. Security review should be repeated before each Play Store release.*
