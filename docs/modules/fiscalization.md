# EFRIS Fiscalization Module

**App**: `fiscalization`
**Type**: Tenant-scoped
**Phase**: P0 (pre-launch blocker)
**Status**: Scaffolded with Mock provider; Weaf provider ready for credentials

---

## Why this exists

URA made EFRIS compliance mandatory for **all fuel retail in Uganda as of 1 July 2025**, regardless of turnover or VAT status. Every sales invoice must be transmitted to URA in real time, receive a Fiscal Document Number (FDN), anti-fake code, and QR code, and all three must be printed on the customer receipt.

Without EFRIS, Nexus ERP cannot legally be sold to a Ugandan fuel station. See `docs/research/efris-integration.md` for the full legal and technical research.

---

## Architecture

### Provider-agnostic design

All fiscalization happens through a `FiscalizationProvider` interface. Swap providers by changing `EfrisConfig.provider` — nothing in the sales or receipt flow needs to change.

```
fiscalization/
├── providers/
│   ├── base.py     # FiscalizationProvider ABC + FiscalResult dataclass
│   ├── mock.py     # MockProvider — dev/test, returns fake FDN/QR
│   ├── weaf.py     # WeafProvider — stub for Weaf Company Uganda API
│   └── (future)    # direct URA, other middleware
├── models.py       # EfrisConfig (singleton), FiscalInvoice
├── services.py     # submit_sale_for_fiscalization, build_payload, retry, get_fiscal_data
├── views.py        # Config CRUD + invoice list/retry endpoints
├── tests.py        # 25 tests
└── management/commands/retry_efris.py  # cron-friendly retry command
```

### Flow

1. `sales.process_checkout()` completes and commits a sale
2. It calls `fiscalization.services.submit_sale_for_fiscalization(sale)` in a try/except
3. That creates a `FiscalInvoice` row, builds the canonical payload, picks the configured provider, and submits
4. **Success** → `status='accepted'`, FDN/QR/verification code stored
5. **Transient failure** (network, 5xx) → `status='failed'`, picked up by `retry_efris` cron
6. **Permanent rejection** (4xx, invalid TIN, etc.) → `status='rejected'`, not retried
7. **Disabled** → `status='skipped'`, no API call made
8. `sale.receipt` endpoint attaches `fiscal` data to the receipt response for any sale with `status='accepted'`

**Critical: fiscalization failures NEVER block a sale.** The sale is always recorded and the fiscal submission happens as a side effect. This protects in-store operations if EFRIS is temporarily unreachable.

---

## Models

### EfrisConfig (singleton per tenant)

| Field | Type | Notes |
|---|---|---|
| tin | CharField(20) | URA Tax Identification Number |
| legal_name | CharField(255) | Name as registered with URA |
| trade_name | CharField(255) | Business trading name |
| provider | CharField | `mock`, `weaf`, or `direct` |
| is_enabled | BooleanField | Master switch |
| weaf_api_key | CharField(255) | Write-only in serializer (not returned in GET) |
| weaf_base_url | URLField | Weaf API base URL |
| default_currency | CharField(3) | Defaults to `UGX` |
| default_tax_rate | Decimal(5,2) | Defaults to 18.00 (VAT) |

**Singleton enforcement**: `save()` forces `pk=1`.

### FiscalInvoice (one per Sale)

| Field | Type | Notes |
|---|---|---|
| sale | OneToOneField(Sale) | PROTECT to prevent orphaning |
| status | CharField | `pending`, `submitted`, `accepted`, `rejected`, `failed`, `skipped` |
| provider | CharField | Which provider handled it |
| fdn | CharField(64) | Fiscal Document Number (indexed) |
| invoice_id | CharField(64) | Provider's invoice reference |
| verification_code | CharField(64) | Anti-fake code |
| qr_code | TextField | QR data (URL or base64) |
| request_payload | JSONField | Full submitted payload (audit) |
| response_payload | JSONField | Full provider response (audit) |
| error_message | TextField | Last error, if any |
| retry_count | PositiveIntegerField | Bounded by `MAX_RETRY_ATTEMPTS=5` |
| submitted_at | DateTimeField | First submission timestamp |
| accepted_at | DateTimeField | Acceptance timestamp |

---

## API Endpoints

### EFRIS Configuration (admin only for writes)
```
GET    /api/fiscalization/config/                      Retrieve tenant config
PATCH  /api/fiscalization/config/1/                    Update (admin only)
POST   /api/fiscalization/config/test-connection/      Run provider health check (admin)
```

### Fiscal Invoices (read-only except retry)
```
GET    /api/fiscalization/invoices/                    List (filterable by status, provider)
GET    /api/fiscalization/invoices/{id}/               Retrieve
POST   /api/fiscalization/invoices/{id}/retry/         Retry a failed invoice (admin/manager)
POST   /api/fiscalization/invoices/retry-all/          Bulk retry (admin/manager)
```

### Receipt integration
```
GET    /api/sales/{id}/receipt/                        Returns sale + fiscal { fdn, qr_code, verification_code, ... }
```

---

## Providers

### MockProvider (default)
- Returns deterministic fake FDN/QR based on the invoice reference (SHA-256 hash)
- No external dependencies
- Use for: development, tests, demos, load testing
- Output: `MOCK-XXXXXXXX` FDN, fake URA verification URL

### WeafProvider (ready for credentials)
- Full HTTP plumbing (auth headers, timeouts, retries, 4xx/5xx handling)
- Requires: `EfrisConfig.weaf_api_key`, `EfrisConfig.weaf_base_url`
- **TODO** once Weaf contract is signed:
    1. Update `endpoint` in `providers/weaf.py` to the real Weaf path
    2. Update response field mapping (currently assumes `fdn`, `invoiceId`, `verificationCode`, `qrCode` keys — confirm against real Weaf docs)
    3. Test against Weaf sandbox first

**Contact Weaf**:
- Phone / WhatsApp: +256 756 508361
- Email: services@weafcompany.com
- Docs (limited public): https://weafmall.com/blog/weaf-efris-api-documentation-seamless-ura-integration-for-uganda-businesses-efris-integration-in-uganda

### Future: Direct URA provider
After Nexus gets URA-accredited (post-revenue, phase 2), a `DirectProvider` can be added that talks directly to `efris.ura.go.ug` and eliminates the Weaf middleman + fees.

---

## Configuration

### To enable fiscalization with mock (for dev):
```bash
curl -X PATCH http://demo.localhost:8000/api/fiscalization/config/1/ \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "tin": "1000000000",
    "legal_name": "Demo Business Ltd",
    "trade_name": "Demo",
    "provider": "mock",
    "is_enabled": true
  }'
```

After this, every checkout will create a `FiscalInvoice` with a fake `MOCK-XXXXXXXX` FDN that appears on the receipt.

### To switch to Weaf (when you have credentials):
```bash
curl -X PATCH http://demo.localhost:8000/api/fiscalization/config/1/ \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "weaf",
    "weaf_api_key": "your-real-key",
    "weaf_base_url": "https://api.weafcompany.com"
  }'
```

Then update `fiscalization/providers/weaf.py` with the real endpoint path and response schema (see TODOs in that file).

---

## Retry queue

Failed submissions are retried by the `retry_efris` management command:

```bash
# Manual one-off
docker compose exec backend python manage.py retry_efris

# Target a specific tenant
docker compose exec backend python manage.py retry_efris --tenant demo

# Production: run every 5 minutes via cron
*/5 * * * * docker compose exec -T backend python manage.py retry_efris --limit 100
```

Up to `MAX_RETRY_ATTEMPTS = 5` retries per invoice. After that, the invoice is left in `failed` status and must be manually retried via the admin UI or the POST `/retry/` endpoint.

---

## Tests

`fiscalization/tests.py` has ~25 tests covering:

- **Config**: singleton, defaults, creation
- **Provider factory**: mock/weaf resolution, unknown provider error
- **MockProvider**: deterministic FDN, success path
- **WeafProvider**: API key/URL required, success mapping, 4xx→rejected, 5xx→retryable
- **Payload builder**: full shape, TIN, items, totals, payments
- **submit_sale_for_fiscalization**: disabled→skipped, success→accepted, rejected, transient→failed, unexpected→failed
- **Retry queue**: success, exhaustion
- **get_fiscal_data**: none when missing, none when not accepted, full data when fiscalized
- **API**: config GET/PATCH permissions, API key not leaked, invoice list, retry endpoint

---

## Security notes

- `weaf_api_key` is `write_only` in the serializer, so it never appears in GET responses
- Only `admin` role can update `EfrisConfig` or trigger manual retries
- `FiscalInvoice` is read-only via the API — no DELETE or PATCH on records
- `request_payload` / `response_payload` contain the full EFRIS payloads; restrict access to admins for GDPR / customer PII reasons (in Uganda, URA mandates 5-year retention of fiscal records)

---

## Migration to direct URA (future)

When Nexus gets URA-accredited:

1. Obtain digital signing certificate from a local CA
2. Add `providers/direct.py` implementing `FiscalizationProvider`
3. Register it in `providers/__init__.py::get_provider_class`
4. Per-tenant, set `EfrisConfig.provider = 'direct'` and configure URA credentials
5. Old Weaf-provider invoices remain untouched; only new sales use direct

No code in `sales/` or receipts needs to change.
