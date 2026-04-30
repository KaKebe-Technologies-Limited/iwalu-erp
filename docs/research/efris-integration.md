# URA EFRIS Integration Research

**Status**: Research complete, pending decision
**Last Updated**: 2026-04-05
**Impact**: Go-to-market blocker — fuel retail mandatory from 1 July 2025

---

## Critical Finding

**EFRIS is legally mandatory for fuel retail in Uganda as of 1 July 2025** (URA expansion to 12 new sectors). This is no longer threshold-based (previously only VAT-registered businesses above UGX 150M turnover). **Every petrol station in Uganda must use EFRIS**, regardless of size, or they cannot legally issue sales receipts.

Nexus ERP cannot launch to fuel stations without EFRIS integration.

---

## How EFRIS Works

EFRIS (Electronic Fiscal Receipting and Invoicing Solution) is URA's real-time fiscalisation system. Every sales invoice must be transmitted to URA's central system, which returns a **Fiscal Document Number (FDN)**, an **InvoiceId**, an **Anti-Fake Code**, and a **QR code**. All four must be printed on the customer receipt.

### Integration modes URA supports

1. **Web Portal / Client App** — manual entry at efris.ura.go.ug (not viable for a POS)
2. **EFD (Electronic Fiscal Device)** — dedicated hardware; issues fiscal receipts
3. **EDC (Electronic Dispenser Controller)** — fuel-pump-specific hardware that monitors nozzle movement and auto-issues e-receipts at the pump. URA's stated expectation for unattended fuel sales.
4. **System-to-System Integration** — ERP/POS connects via JSON API. This is the correct mode for a SaaS ERP.

### Payload (per invoice)

Encrypted JSON containing:
- Seller TIN
- Buyer details (TIN + legal name, or "Final Consumer")
- Line items: code, description, quantity, unit price, tax category
- Tax breakdowns (VAT 18% / exempt / zero)
- Totals, currency, payment mode
- Goods/services classification codes

Response structure: `data`, `globalInfo`, `returnStateInfo`.

---

## Certification Path

URA maintains an official "List of Accredited EFRIS Software Integrators" (last public version April 2024). To become accredited:

1. Apply to URA
2. Complete the EFRIS Integration UAT Readiness Checklist
3. Pass User Acceptance Testing in URA's sandbox
4. Obtain a digital signing certificate from a local CA
5. Get listed as an accredited integrator

**Timelines and fees are not publicly documented.** Anecdotally weeks to months. No published SLA.

---

## Build vs. Partner Decision

### Option A — Direct integration (build our own)

**Pros**
- Full control of fiscalisation logic and latency
- No per-invoice fees
- Differentiation moat (listed accredited integrator status)
- Can offer EFRIS as a feature to other ERPs later

**Cons**
- Accreditation overhead (weeks-months, unclear fees)
- Must manage digital signing certificate lifecycle
- Must track URA schema changes over time
- Still doesn't solve the EDC-at-pump hardware question
- Delays go-to-market

### Option B — Partner with middleware provider

Confirmed options:
- **Weaf (Weafmall)** — Ugandan, published REST wrapper, multi-language SDK, documented
- **EDICOM** — global e-invoicing provider with Uganda EFRIS coverage
- **Tally Solutions** — has EFRIS but it's embedded in Tally ERP, not a standalone API
- **Osela Technologies** — SAP B1 integrator (not a general API)
- **Yanolja Cloud Solution**, **Gopus**, **Melasoft**, **Voxel Group** — regional

**Pros**
- Fastest time-to-market
- Accreditation umbrella (provider is the listed integrator)
- Provider handles schema changes and certificate rotation
- Lower upfront engineering cost

**Cons**
- Per-invoice or subscription fees erode SaaS margins
- Dependency risk (provider pricing changes, outages, shutdown)
- Less differentiation

### Recommendation

**Hybrid approach — Start with Weaf, plan direct integration as Phase 2.**

1. **Phase 1 (launch)**: Integrate with Weaf EFRIS API. Ship fast, start onboarding customers, generate revenue.
2. **Phase 2 (post-revenue)**: Apply for URA accreditation in parallel with operations. Once accredited, migrate to direct integration to eliminate per-invoice fees and own the stack.
3. **EDC (pump hardware)**: Remains the customer's/URA's procurement responsibility. Nexus integrates with EDC output where possible but does not sell the hardware.

This minimises time-to-market while preserving the option to build a direct integration later as a differentiation moat.

---

## Implementation Plan (Phase 1: Weaf-backed)

### New Django app: `fiscalization`

**Models**
- `FiscalInvoice` — links a `sales.Sale` to an EFRIS transmission
- fields: sale FK, tin, status (pending/submitted/accepted/failed), fdn, invoice_id, verification_code, qr_code, submitted_at, response_raw (JSON), retry_count
- `EfrisConfig` — tenant-level credentials (Weaf API key, seller TIN, goods classification codes)
- `EfrisRetryQueue` — failed submissions for async retry

**Services**
- `submit_invoice(sale)` — builds payload, calls Weaf API, records response
- `retry_failed(limit=100)` — periodic retry of pending/failed submissions
- `get_fiscal_data(sale)` — returns FDN + QR code for receipt printing

**Integration with sales**
- `sales/services.py::process_checkout()` already creates the sale. After commit, enqueue `submit_invoice` (synchronously for now; Celery in phase 2).
- `SaleViewSet.receipt` endpoint includes fiscal data when available.
- If EFRIS submission fails: sale is still recorded, fiscal data is pending, retry queue picks it up.

**Tenant config**
- `SystemConfig` adds `efris_tin`, `efris_enabled`, `efris_provider` fields
- `/api/system-config/` extended with EFRIS settings (admin only)

**Tests**
- Mock Weaf API responses
- Unit tests for payload building
- Integration test for checkout → fiscalization flow
- Retry queue test

### What we need from stakeholders before coding

1. **Seller TIN** — each tenant needs their own URA TIN configured
2. **Weaf contract** — pricing, sandbox access, API key procurement
3. **Goods classification codes** — URA-published codes for petrol, diesel, kerosene, lubricants
4. **Test TIN + sandbox credentials** — for dev/CI
5. **Legal review** — data residency, encryption requirements, receipt retention (URA typically requires 5 years)

---

## Sources

- [URA EFRIS portal](https://efris.ura.go.ug/)
- [URA EFRIS overview](https://ura.go.ug/en/efris/)
- [EFRIS Handbook 2024-25](https://ura.go.ug/storage/2025/01/THE-EFRIS-HANDBOOK-2024-25-2.pdf)
- [EFRIS UAT Readiness Checklist](https://ura.go.ug/en/download/efris-system-to-system-integration-uat-readiness-checklist/)
- [URA Accredited EFRIS Software Integrators (Apr 2024)](https://ura.go.ug/en/download/list-of-accredited-efris-software-integrators-as-at-16-april-2024/)
- [URA expands EFRIS to 12 new sectors incl. fuel (CEO East Africa)](https://www.ceo.co.ug/ura-expands-efris-compliance-to-12-new-sectors-in-sweeping-tax-digitisation-move/)
- [EDICOM EFRIS guide](https://edicomgroup.com/blog/electronic-invoicing-in-uganda-the-efris-system)
- [Weaf EFRIS API docs](https://weafmall.com/blog/weaf-efris-api-documentation-seamless-ura-integration-for-uganda-businesses-efris-integration-in-uganda)
- [Cleartax — e-Invoicing Uganda](https://www.cleartax.com/ug/e-invoicing-uganda)
- [PwC Uganda — EFRIS compliance](https://www.pwc.com/ug/en/press-room/efris-compliance.html)
