# Payments Module

The Payments module provides a unified interface for handling mobile money (MTN, Airtel) and card payments (via Pesapal). It supports both direct API integrations and aggregator-based flows.

## 1. Architecture

The module follows a provider-agnostic architecture using a factory pattern.

- **`PaymentConfig`**: Singleton model storing tenant-level credentials for all providers.
- **`PaymentTransaction`**: Tracks every payment attempt, its status, and audit logs.
- **`PaymentProvider`**: Base class for all implementation adapters (MTN, Airtel, Pesapal, Mock).
- **`services.py`**: High-level API for initiating payments and handling callbacks.

## 2. Supported Providers

| Provider | Methods | Description |
|----------|---------|-------------|
| `mtn` | Mobile Money | Direct MTN MoMo Collections (USSD push). |
| `airtel` | Mobile Money | Direct Airtel Money Collections (USSD push). |
| `pesapal` | Cards, MM, Bank | Aggregator. Provides a `redirect_url` for the customer. |
| `mock` | All | Development/testing provider that succeeds immediately. |

## 3. Endpoints

### Configuration (`/api/payments/config/`)
- `GET /`: Retrieve the current configuration (secrets masked).
- `PATCH /1/`: Update configuration (admin only).

### Transactions (`/api/payments/transactions/`)
- `GET /`: List all transactions (filterable by status, provider, sale).
- `GET /{id}/`: Retrieve details of a specific transaction.
- `POST /{id}/refresh_status/`: Force-poll the provider for the latest status.

### Functional Endpoints (`/api/payments/`)
- `POST /initiate/`: Start a new payment.
- `GET/POST /callback/{provider}/`: Webhook endpoint for provider notifications.

## 4. Integration Flow

1. **Initiate**: Call `POST /api/payments/initiate/`.
2. **Handle Response**:
   - For `mtn`/`airtel`: Wait for customer to approve on their handset.
   - For `pesapal`: Redirect the user to the `redirect_url` provided in the response.
3. **Verify**:
   - The system handles webhooks automatically.
   - For UI feedback, poll `GET /api/payments/transactions/{id}/` or use the `refresh_status` action.

## 5. Development & Testing

Use the `mock` provider with specific amounts to test different outcomes:
- `.01` → FAILED
- `.02` → CANCELLED
- `.03` → EXPIRED
- `.99` → PROCESSING (transitions to SUCCESS on next status query)
