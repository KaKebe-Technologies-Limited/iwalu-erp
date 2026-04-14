# Frontend Developer Guide — Pending Integrations

**Last Updated**: April 2026
**Context**: Backend for Phases 1-6 is complete. This guide covers the remaining integration work for the frontend.

---

## 1. Role-Based Dashboard Access (Permissions)

**Context**: Backend supports fine-grained permissions to control dashboard visibility. Use this to hide sidebar items and buttons the user shouldn't see.

### 1.1 Fetching Permissions
Call this immediately after login (or on page refresh).

**Endpoint**: `GET /api/auth/me/permissions/`

**Response**:
```json
{
  "role": "cashier",
  "sections": ["dashboard", "pos", "sales", "shifts", "products", "fuel", "notifications"],
  "actions": ["open_shift", "close_shift", "process_sale"]
}
```

### 1.2 Implementation Pattern
1.  Store the `permissions` object in your Zustand auth store.
2.  **Sidebar**: Only show items present in the `sections` array.
3.  **Feature Gating**: Use the `actions` array to show/hide specific buttons (e.g., only show "Void Sale" if `void_sale` is in the `actions` array).

---

## 2. Payments Module Integration (Phase 6c/d)

**Context**: Backend for integrated payments (MTN, Airtel, Pesapal) and disbursements is complete.

### 2.1 Payment Configuration (`/dashboard/settings/payments`)
Admin page to configure credentials for providers.
- **Endpoint**: `GET/PATCH /api/payments/config/`
- **Security**: Secrets are write-only. They won't be returned by the API once saved.

### 2.2 Initiating a Collection (Customer Paying)
**Endpoint**: `POST /api/payments/initiate/`

**Payload**:
```typescript
interface InitiatePaymentRequest {
  amount: string;          // e.g. "50000.00"
  method: 'mobile_money' | 'card' | 'bank';
  provider?: 'mtn' | 'airtel' | 'pesapal' | 'mock';
  phone_number?: string;   // Required for mobile_money
  customer_email?: string;
  customer_name?: string;
  description?: string;
  sale_id?: number;
}
```

### 2.3 Initiating a Disbursement (Paying Out)
**Endpoint**: `POST /api/payments/disburse/`

**Payload**:
```typescript
interface InitiateDisbursementRequest {
  amount: string;
  method: 'mobile_money';
  provider?: 'mtn' | 'airtel' | 'mock';
  phone_number: string;
  customer_name?: string;
  description?: string;
}
```

### 2.4 Status Polling
**Endpoint**: `POST /api/payments/transactions/{id}/refresh_status/`
Returns the updated `PaymentTransaction`. Check `status` for `success` or `failed`.

---

## 3. Platform Admin Dashboard (Spec Only)

**Context**: Separate UI for Kakebe Technologies to manage all business tenants.

### Key views
- List all businesses/tenants
- Create new tenant (provision schema)
- Suspend/activate tenant
- Cross-tenant analytics

---

## 4. Shared TypeScript Interfaces

```typescript
interface PaymentTransaction {
  id: number;
  transaction_type: 'collection' | 'disbursement';
  provider: 'mock' | 'mtn' | 'airtel' | 'pesapal';
  status: 'pending' | 'processing' | 'success' | 'failed' | 'cancelled' | 'expired';
  is_terminal: boolean;
  amount: string;
  currency: string;
  phone_number: string;
  reference: string;
  provider_transaction_id: string;
  response_payload: any;
  error_message: string;
  created_at: string;
}
```
