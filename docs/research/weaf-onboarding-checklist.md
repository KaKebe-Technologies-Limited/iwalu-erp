# Weaf Credentials — Integration Checklist

**Status**: Awaiting Weaf signup completion + sandbox credentials
**Owner**: Backend
**Estimated effort once credentials are in hand**: 2-4 hours of code + 1-2 days of sandbox testing

This document is the exact step-by-step list of changes needed to flip Nexus ERP from the `MockProvider` to a working **Weaf production integration**. Everything here is concrete — no architecture decisions remaining.

---

## Prerequisites — What to obtain from Weaf

Contact Weaf and confirm/collect ALL of the following before starting:

### Credentials
- [ ] **Sandbox API key** (for dev/CI/QA testing)
- [ ] **Production API key** (for live tenants — store separately, do NOT commit)
- [ ] **Sandbox base URL** (e.g. `https://sandbox.weafcompany.com` or similar)
- [ ] **Production base URL**
- [ ] **Auth scheme** — confirm whether it's `Bearer <key>`, `X-API-Key: <key>`, HMAC-signed requests, or OAuth2 (the stub assumes `Bearer`)

### Endpoint contract
- [ ] **POST endpoint path** for submitting an invoice (the stub assumes `/api/efris/invoices` — replace if different)
- [ ] **Request schema** — exact JSON shape Weaf expects. Map fields against `fiscalization/services.py::build_payload`
- [ ] **Response schema** — exact JSON shape on success. Identify which keys map to:
    - FDN (Fiscal Document Number from URA)
    - Provider invoice ID
    - Verification / anti-fake code
    - QR code (URL or base64?)
- [ ] **Error response shape** — what 4xx/5xx bodies look like
- [ ] **Health check endpoint** (the stub assumes `/api/health`)

### Operational
- [ ] **Pricing** — per-invoice fee, monthly/annual subscription, free tier limits, overage costs
- [ ] **Rate limits** — requests per second/minute/day
- [ ] **SLA / uptime guarantee** — important for retry logic tuning
- [ ] **Webhook support** — does Weaf push status updates, or is it strictly request/response?
- [ ] **Sandbox TIN** — a test TIN to use for dev/QA without affecting real tax records
- [ ] **Goods classification codes** — URA-published codes for petrol, diesel, kerosene, lubricants, lubes, and any non-fuel SKUs you sell. These get embedded in line items.
- [ ] **5-year retention requirement confirmation** — URA mandates fiscal record retention; confirm Weaf handles this server-side or whether Nexus must store the full audit trail

---

## Code changes — file by file

Once credentials and the API contract are in hand, exactly these files need editing:

### 1. `backend/fiscalization/providers/weaf.py`

**Change 1 — Endpoint path** (line ~60):
```python
endpoint = f'{self.base_url}/api/efris/invoices'
```
→ Replace `/api/efris/invoices` with the real path Weaf gave you.

**Change 2 — Auth header** (line ~38, `_headers` method):
```python
return {
    'Authorization': f'Bearer {self.api_key}',
    ...
}
```
→ If Weaf uses a different scheme (`X-API-Key`, HMAC signature, OAuth2 bearer), update here.

**Change 3 — Response field mapping** (lines ~85-92):
```python
return FiscalResult(
    success=True,
    fdn=str(data.get('fdn', '')),
    invoice_id=str(data.get('invoiceId', '')),
    verification_code=str(data.get('verificationCode', '')),
    qr_code=str(data.get('qrCode', '')),
    raw_response=data,
)
```
→ Update each `data.get('...')` key to match the real Weaf response keys. Watch for nested objects (e.g. `data['result']['fdn']`).

**Change 4 — Health check path** (line ~100):
```python
response = requests.get(f'{self.base_url}/api/health', ...)
```
→ Replace with real health endpoint, or remove the override if Weaf doesn't expose one (the base class returns `True` by default).

### 2. `backend/fiscalization/services.py::build_payload`

The current canonical payload uses generic field names (`invoiceReference`, `seller`, `buyer`, `items`, etc.). If Weaf wants a different shape (snake_case, nested wrappers, different key names), the cleanest fix is to **transform inside `WeafProvider.submit_invoice`** rather than changing `build_payload` — this keeps the canonical shape provider-agnostic for future direct-URA work.

Add a `_to_weaf_shape(payload)` method in `weaf.py` if needed:

```python
def _to_weaf_shape(self, canonical_payload: dict) -> dict:
    """Map canonical payload → Weaf-specific JSON schema."""
    return {
        # ... reshape here
    }
```

Then call it inside `submit_invoice`:
```python
weaf_payload = self._to_weaf_shape(payload)
response = requests.post(endpoint, json=weaf_payload, ...)
```

### 3. Goods classification codes

URA requires classification codes per line item. There are two reasonable places to store these:

**Option A** — Add to `products.Product`:
```python
# backend/products/models.py
ura_classification_code = models.CharField(max_length=20, blank=True)
```
Then in `build_payload`, include `'classificationCode': item.product.ura_classification_code`.

This is the right answer long-term. It needs a migration and an admin/API update.

**Option B** — Hard-code per business unit in `EfrisConfig`:
A JSONField like `default_classification_codes = {'fuel': '...', 'lubricant': '...'}` and look up by `category.business_unit`. Faster, dirtier, fine for launch.

**Recommendation**: Option A. Add the field to `Product`, update the products serializer/admin, write a data migration that backfills codes for existing products from a CSV or default mapping. Manager-level users should be able to edit the code per product via the existing products page.

### 4. Tenant configuration

Each tenant needs their **own** Weaf API key and TIN. This is already supported — `EfrisConfig` is per-tenant. After deploying:

```bash
curl -X PATCH http://<tenant>.nexuserp.com/api/fiscalization/config/1/ \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "tin": "1234567890",
    "legal_name": "Customer Business Ltd",
    "trade_name": "CustomerName",
    "provider": "weaf",
    "weaf_api_key": "<their key OR our shared key>",
    "weaf_base_url": "https://api.weafcompany.com",
    "is_enabled": true
  }'
```

**Critical decision**: do all tenants use Nexus's master Weaf account, or does each tenant bring their own Weaf account?
- **Master account (Nexus)**: simpler onboarding, Nexus pays Weaf and bills tenants. Risk: Nexus is the contractual party.
- **Per-tenant accounts**: each business signs up with Weaf separately, brings their own key. Nexus is just a passthrough integrator. Lower legal risk, more onboarding friction.

This is a **business decision** — discuss with Kakebe before launch. The architecture supports both today.

### 5. Tests

Update `fiscalization/tests.py::WeafProviderTests` to use the real response shape:

```python
mock_post.return_value.json.return_value = {
    # ... copy the actual Weaf success response shape here
}
```

Then add 1-2 integration tests against the **sandbox** (not unit tests — these hit real Weaf and should be marked `@override_settings` or skipped in CI unless `WEAF_SANDBOX_KEY` env is present):

```python
import os
import unittest

@unittest.skipUnless(
    os.getenv('WEAF_SANDBOX_KEY'),
    'WEAF_SANDBOX_KEY not set; skipping live sandbox test',
)
class WeafSandboxIntegrationTest(TestCase):
    def test_real_sandbox_submission(self):
        # ... configure EfrisConfig with sandbox creds
        # ... build a real payload from a fixture sale
        # ... assert the response contains an FDN
```

CI runs these only when the secret is present in GitHub Actions / your CI provider.

### 6. Secrets management

Do **not** commit Weaf API keys to git. Two options:

- **Per-tenant** (preferred): keys live in `EfrisConfig.weaf_api_key` in the tenant DB. Already write-only in the serializer, so they don't leak in GET responses. Encryption at rest is the DB's responsibility (use AWS RDS encryption, GCP Cloud SQL CMEK, etc.)
- **Global fallback**: add `WEAF_API_KEY` to backend `.env`, expose via settings, and have `WeafProvider` fall back to it if `config.weaf_api_key` is empty. Useful if Nexus runs a master account.

For production, migrate to a real vault (Doppler, AWS Secrets Manager, HashiCorp Vault) — already noted in `MEMORY.md`.

### 7. Receipt template (frontend dev's job)

The receipt endpoint (`GET /api/sales/{id}/receipt/`) now returns a `fiscal` block when fiscalization is accepted:

```json
{
  "id": 42,
  "receipt_number": "OUT1-20260406-0001",
  ...,
  "fiscal": {
    "fdn": "WEAF-XXXXXXXX",
    "invoice_id": "INV-99",
    "verification_code": "ABC123",
    "qr_code": "https://efris.ura.go.ug/...",
    "accepted_at": "2026-04-06T15:30:00+03:00"
  }
}
```

The frontend dev needs to update the receipt printing template to render:
- The FDN at the bottom of the receipt ("URA Receipt: WEAF-XXXXXXXX")
- The verification code
- A QR code rendered from the `qr_code` URL/data (using `qrcode.react` or similar)

If the `fiscal` block is absent, render nothing (or a "Receipt pending fiscalization" notice for failed/pending invoices).

---

## Rollout plan

1. **Sandbox phase** (1 day)
   - Configure one dev tenant with sandbox Weaf credentials
   - Make 5-10 test sales of varying sizes/items
   - Verify FDN, QR, verification code returned and stored correctly
   - Verify retry queue handles forced 5xx responses
   - Verify rejected payloads (bad TIN) get marked `rejected` with no retry

2. **Pilot phase** (1 week)
   - Onboard 1 friendly customer (lighthouse) to Weaf with their real TIN
   - Monitor `FiscalInvoice` table for failures, retry counts, error patterns
   - Set up Slack/email alert from `notify_variance_alert` style trigger when fiscalization fails > N times in M minutes

3. **General rollout**
   - Open to all tenants
   - Enable fiscalization by default for new tenants in the `register_tenant` flow
   - Document EFRIS as a feature in the proposal docx + marketing site

---

## Things that might bite you

- **TIN validation**: URA TINs are 10 digits. Reject invalid TINs at config time, not at submission time.
- **Currency**: URA expects UGX. Multi-currency support is a future feature; for now hard-code UGX in the canonical payload (already done via `default_currency`).
- **Tax exemptions**: not all products are 18% VAT. Some fuels have specific excise duties. Confirm with URA + tenant accountants what tax rates apply per product category. The `tax_rate` field on Product handles per-product overrides.
- **Voided sales**: if a sale is voided after fiscalization, EFRIS expects a credit note (negative invoice). We do NOT yet handle this — there's a TODO. When you void a sale post-fiscalization, generate a `FiscalInvoice` of type `credit_note` referencing the original FDN. Track this as a follow-up task.
- **Network outages at the pump**: if the internet drops, sales must still work (offline-first per the proposal). Fiscalization will queue and retry. The receipt printed at the time of sale will lack the FDN; add a "fiscal pending" stamp and reprint once the FDN arrives. This is a UX requirement the frontend must handle.
- **5-year retention**: URA mandates 5 years of fiscal record retention. Ensure backups cover this.
- **Customer TIN capture**: businesses sometimes want a B2B receipt with the buyer's TIN on it. Today we hard-code `FINAL_CONSUMER`. Add an optional `buyer_tin` field to the checkout API if/when needed.

---

## Files to touch (summary)

| File | Change |
|---|---|
| `fiscalization/providers/weaf.py` | Endpoint path, auth header, response field mapping, optionally `_to_weaf_shape` method |
| `fiscalization/services.py` | Only if classification codes need to be added to `build_payload` |
| `fiscalization/tests.py` | Update mocked Weaf response shape; add optional sandbox integration tests |
| `products/models.py` | Add `ura_classification_code` field (Option A) |
| `products/migrations/000X_*.py` | Migration for the new field + data backfill |
| `products/serializers.py` | Expose the new field |
| `products/admin.py` | Editable in admin |
| `.env` (not committed) | Per-tenant or global Weaf credentials |
| Frontend receipt template | Render fiscal block (frontend dev) |

---

## When all of this is done

- Update `STATUS.md`: change EFRIS line from "in progress" to "production-ready (Weaf)"
- Update `docs/modules/fiscalization.md`: remove the TODOs, add real Weaf endpoint examples
- Update `Nexus ERP – Full System Proposal.docx`: add EFRIS as a shipped feature in the Tax Authority Integration section
- Save a memory note that Weaf integration is live, and what the per-tenant onboarding command looks like
- Notify the frontend dev that the receipt template needs updating
