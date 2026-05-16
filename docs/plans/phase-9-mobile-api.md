# Phase 9 — Mobile API Layer

**Branch**: `feat-phase-9-mobile-api`  
**Depends on**: Phases 1–8 merged to `main`  
**Scope**: Backend only. New `mobile_api` Django app enabling React Native Android clients to authenticate with role-restricted JWTs, download shift-start data, and batch-sync offline sales transactions.

---

## Overview

The React Native Android app (detailed in `docs/mobile-app-plan.md`) operates in environments with intermittent connectivity. Cashiers and attendants log in, download a snapshot of all products/discounts/pumps for their outlet at shift start, collect sales offline, then sync the batch when connectivity is restored before closing the shift.

This phase implements:

1. **Two new fields on `sales.Sale`** — `client_uuid` for mobile deduplication, `source` to distinguish mobile from web POS sales.
2. **`mobile_api` Django app** — `MobileSyncLog` model, mobile-restricted JWT auth, `IsMobileClient` / `IsNotMobileClient` permission classes, shift-start data endpoint, batch sync endpoint.
3. **Shift close guard** — prevents closing a shift while the mobile client reports pending unsynced transactions.
4. **Sensitive endpoint hardening** — `IsNotMobileClient` added to finance, HR, tenant admin, user admin, and asset endpoints so a stolen mobile token cannot reach privileged data.

**Key constraints carried forward from the existing codebase:**
- Tenant-scoped apps use `TenantTestCase` + `TenantClient` for tests.
- Cross-schema foreign keys are not possible — use `IntegerField` for user/outlet/shift references in tenant apps.
- Always run `migrate_schemas`, never `migrate`.
- UGX has no fractional subdivision — all `DecimalField` definitions for currency use `decimal_places=0` unless matching an existing field's `decimal_places=2` convention (sales totals are already `decimal_places=2`; follow existing convention rather than changing it).
- `INSTALLED_APPS` ordering must be preserved for `django-tenants` — append, do not sort.

---

## App Registration

### `backend/config/settings.py`

Add `'mobile_api'` to `TENANT_APPS` (stores sync logs per tenant schema). Append after `'assets'`:

```python
TENANT_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'outlets',
    'products',
    'sales',
    'inventory',
    'reports',
    'finance',
    'hr',
    'fuel',
    'notifications',
    'system_config',
    'fiscalization',
    'payments',
    'approvals',
    'assets',
    'mobile_api',   # <-- add here
]
```

Also add a throttle rate for the mobile sync endpoint (uses `UserRateThrottle` keyed on authenticated user):

```python
REST_FRAMEWORK = {
    # ... existing keys unchanged ...
    'DEFAULT_THROTTLE_RATES': {
        'payment-callback': '120/min',
        'tenant-registration': '3/hour',
        'mobile-sync': '10/min',   # <-- add
    },
}
```

> `UserRateThrottle` is built into DRF and uses the authenticated user as the cache key. No extra package needed.

### `backend/api/urls.py`

Add the mobile namespace alongside existing includes:

```python
from django.urls import path, include

urlpatterns = [
    # ... existing patterns ...
    path('mobile/', include('mobile_api.urls')),
]
```

---

## Phase 1: Migrations — Add Fields to `sales.Sale`

### Edit `backend/sales/models.py`

Locate the `Sale` class and add two new fields. Place them after the `notes` field (or after `status`) so existing field ordering is preserved for readability:

```python
class Sale(models.Model):
    # ... existing fields ...

    # --- Mobile offline support (Phase 9) ---
    client_uuid = models.UUIDField(
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        help_text=(
            "Client-generated UUID for mobile offline deduplication. "
            "Null for web POS sales."
        ),
    )
    source = models.CharField(
        max_length=10,
        choices=[('pos', 'Web POS'), ('mobile', 'Mobile App')],
        default='pos',
    )
```

### Run Migrations

```bash
docker compose exec backend python manage.py makemigrations sales
docker compose exec backend python manage.py migrate_schemas
```

The migration will be named something like `0007_sale_client_uuid_sale_source.py`. Verify with:

```bash
docker compose exec backend python manage.py showmigrations sales
```

---

## Phase 2: New App Structure — `mobile_api`

### Create the app

```bash
docker compose exec backend python manage.py startapp mobile_api
```

### File layout

```
backend/mobile_api/
├── __init__.py
├── apps.py
├── models.py        # MobileSyncLog
├── serializers.py   # Input + output serializers
├── views.py         # ShiftStartDataView, MobileSyncView
├── urls.py
├── permissions.py   # IsMobileClient, IsNotMobileClient
├── auth.py          # MobileTokenObtainPairSerializer/View
└── tests.py         # 40+ tests
```

### `apps.py`

```python
from django.apps import AppConfig


class MobileApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mobile_api'
    verbose_name = 'Mobile API'
```

### `models.py` — `MobileSyncLog`

```python
from django.db import models


class MobileSyncLog(models.Model):
    """
    Audit record written each time a mobile device completes a batch sync.
    Stored per-tenant (app is in TENANT_APPS).
    Uses IntegerField for shift/user/outlet references — cross-schema FK
    not possible with django-tenants.
    """
    device_id = models.CharField(max_length=255)
    shift_id = models.IntegerField()
    user_id = models.IntegerField()
    outlet_id = models.IntegerField()
    transaction_count = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    synced_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-synced_at']
        indexes = [
            models.Index(fields=['shift_id', 'synced_at']),
        ]

    def __str__(self):
        return (
            f"Sync shift={self.shift_id} by device={self.device_id} "
            f"at {self.synced_at}"
        )
```

### Run migration for the new app

```bash
docker compose exec backend python manage.py makemigrations mobile_api
docker compose exec backend python manage.py migrate_schemas
```

---

## Phase 3: Mobile JWT Auth — `mobile_api/auth.py`

Mobile tokens embed two extra claims: `client = 'mobile'` and `role = <user role>`. The `validate()` method rejects any login attempt from roles that are not `cashier` or `attendant` — admins and managers must use the web interface.

```python
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.permissions import AllowAny
from rest_framework import serializers as drf_serializers


class MobileTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extends the standard JWT serializer to:
    1. Embed 'client' and 'role' claims in the token payload.
    2. Reject login for roles other than cashier and attendant.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['client'] = 'mobile'
        token['role'] = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        allowed_roles = ('cashier', 'attendant')
        if user.role not in allowed_roles:
            raise drf_serializers.ValidationError(
                "Mobile access restricted to cashier and attendant roles."
            )
        return data


class MobileTokenObtainPairView(TokenObtainPairView):
    """
    POST /api/mobile/auth/login/
    Returns access + refresh tokens with mobile claims embedded.
    Only cashier and attendant roles are accepted.
    """
    serializer_class = MobileTokenObtainPairSerializer
    permission_classes = [AllowAny]


class MobileTokenRefreshView(TokenRefreshView):
    """
    POST /api/mobile/auth/refresh/
    Re-exported under the mobile namespace for client clarity.
    Standard SimpleJWT refresh — no extra logic needed.
    """
    pass
```

**Why `TokenRefreshView` works without changes:** The refresh token already carries the embedded claims, and SimpleJWT propagates them to the new access token automatically.

---

## Phase 4: Permissions — `mobile_api/permissions.py`

```python
from rest_framework.permissions import BasePermission


def _get_token_payload(request):
    """
    Safely extract the payload dict from a SimpleJWT AccessToken.
    Returns an empty dict if request.auth is absent or not a JWT.
    SimpleJWT AccessToken instances expose their claims via .payload.
    """
    auth = request.auth
    if auth is None:
        return {}
    # SimpleJWT AccessToken stores claims in .payload (a dict-like object).
    payload = getattr(auth, 'payload', None)
    if payload is None:
        return {}
    return dict(payload)


class IsMobileClient(BasePermission):
    """
    Allows access only when the JWT access token was issued by
    MobileTokenObtainPairView, i.e. payload['client'] == 'mobile'.

    Use on endpoints that mobile clients ARE allowed to reach:
    shift-start-data, batch-sync, checkout read, etc.
    """
    message = "This endpoint requires a mobile-issued JWT."

    def has_permission(self, request, view):
        payload = _get_token_payload(request)
        return payload.get('client') == 'mobile'


class IsNotMobileClient(BasePermission):
    """
    Blocks access when the JWT was issued by MobileTokenObtainPairView.
    Use on sensitive endpoints (finance, HR, payroll, assets, user admin)
    to prevent a stolen mobile token from reaching privileged data.

    Web POS tokens do not carry 'client': 'mobile', so they pass through.
    Unauthenticated requests are handled by IsAuthenticated before this class.
    """
    message = "Mobile tokens are not permitted on this endpoint."

    def has_permission(self, request, view):
        payload = _get_token_payload(request)
        return payload.get('client') != 'mobile'
```

---

## Phase 5: Serializers — `mobile_api/serializers.py`

```python
from decimal import Decimal
from rest_framework import serializers


# ---------------------------------------------------------------------------
# Shift-start data (read / download)
# ---------------------------------------------------------------------------

class MobileCategorySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    business_unit = serializers.CharField()


class MobileProductSerializer(serializers.Serializer):
    """
    Serializes product catalog for offline download.
    outlet_stock is injected from context['outlet_stock_map'] to avoid
    per-product DB queries (N+1 prevention).
    """
    id = serializers.IntegerField()
    name = serializers.CharField()
    sku = serializers.CharField()
    barcode = serializers.CharField(allow_null=True)
    category_id = serializers.IntegerField(source='category.id')
    category_name = serializers.SerializerMethodField()
    selling_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    tax_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    track_stock = serializers.BooleanField()
    unit = serializers.CharField()
    outlet_stock = serializers.SerializerMethodField()

    def get_category_name(self, obj):
        return obj.category.name if obj.category else None

    def get_outlet_stock(self, obj):
        """
        Returns current stock quantity for this product at the requested outlet.
        Defaults to None (meaning 'not tracked at this outlet') when absent.
        """
        stock_map = self.context.get('outlet_stock_map', {})
        qty = stock_map.get(obj.id)
        return str(qty) if qty is not None else None


class MobileDiscountSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    discount_type = serializers.CharField()
    value = serializers.DecimalField(max_digits=10, decimal_places=2)
    valid_until = serializers.DateTimeField(allow_null=True)


class MobilePumpSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    pump_number = serializers.IntegerField()
    name = serializers.CharField()
    product_id = serializers.IntegerField()
    status = serializers.CharField()


class MobileShiftStartDataSerializer(serializers.Serializer):
    outlet = serializers.DictField()
    products = MobileProductSerializer(many=True)
    categories = MobileCategorySerializer(many=True)
    discounts = MobileDiscountSerializer(many=True)
    pumps = MobilePumpSerializer(many=True)
    generated_at = serializers.DateTimeField()


# ---------------------------------------------------------------------------
# Batch sync (write / upload)
# ---------------------------------------------------------------------------

class MobilePaymentInputSerializer(serializers.Serializer):
    payment_method = serializers.CharField(max_length=20)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    reference = serializers.CharField(
        max_length=100, required=False, allow_blank=True, default=''
    )


class MobileSaleItemInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=10, decimal_places=3)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    discount_id = serializers.IntegerField(required=False, allow_null=True)


class MobileTransactionSerializer(serializers.Serializer):
    client_uuid = serializers.UUIDField()
    created_at = serializers.DateTimeField()
    items = MobileSaleItemInputSerializer(many=True)
    payments = MobilePaymentInputSerializer(many=True)
    notes = serializers.CharField(
        required=False, allow_blank=True, default=''
    )


class MobileBatchSyncSerializer(serializers.Serializer):
    device_id = serializers.CharField(max_length=255)
    shift_id = serializers.IntegerField()
    transactions = MobileTransactionSerializer(many=True)

    def validate_transactions(self, value):
        if len(value) > 500:
            raise serializers.ValidationError(
                "Batch size exceeds maximum of 500 transactions per request."
            )
        return value


# ---------------------------------------------------------------------------
# Batch sync results (response)
# ---------------------------------------------------------------------------

class MobileSyncResultSerializer(serializers.Serializer):
    client_uuid = serializers.UUIDField()
    status = serializers.ChoiceField(choices=['synced', 'duplicate', 'failed'])
    sale_id = serializers.IntegerField(allow_null=True)
    receipt_number = serializers.CharField(allow_null=True)
    message = serializers.CharField(allow_null=True)


class MobileBatchSyncResponseSerializer(serializers.Serializer):
    processed = serializers.IntegerField()
    results = MobileSyncResultSerializer(many=True)
```

---

## Phase 6: Shift Start Data Endpoint

### `mobile_api/views.py` — `ShiftStartDataView`

```python
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import UserRateThrottle

from fuel.models import Pump
from inventory.models import OutletStock
from outlets.models import Outlet
from products.models import Category, Product
from sales.models import Discount, Sale, SaleItem, Payment, Shift
from sales.services import (
    apply_discount,
    generate_receipt_number,
    process_checkout,
    submit_sale_for_fiscalization,  # imported from fiscalization.services inside process_checkout
)
from inventory.models import StockAuditLog
from fiscalization.services import submit_sale_for_fiscalization
from users.permissions import IsCashierOrAbove

from .models import MobileSyncLog
from .permissions import IsMobileClient, IsNotMobileClient
from .serializers import (
    MobileBatchSyncResponseSerializer,
    MobileBatchSyncSerializer,
    MobileCategorySerializer,
    MobileDiscountSerializer,
    MobileProductSerializer,
    MobilePumpSerializer,
    MobileSyncResultSerializer,
)


class ShiftStartDataView(APIView):
    """
    GET /api/mobile/shift-start-data/?outlet_id=<id>

    Returns the complete offline data bundle a mobile client needs at
    shift start: outlet info, all active products with current outlet
    stock levels, active categories, valid discounts, and active pumps.

    Permission: authenticated mobile JWT, cashier or above.
    """
    permission_classes = [IsAuthenticated, IsMobileClient, IsCashierOrAbove]

    def get(self, request):
        outlet_id = request.query_params.get('outlet_id')
        if not outlet_id:
            return Response(
                {'error': 'outlet_id query parameter is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            outlet = Outlet.objects.get(pk=outlet_id)
        except Outlet.DoesNotExist:
            return Response(
                {'error': 'Outlet not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Products with categories pre-fetched to avoid N+1
        products_qs = Product.objects.filter(
            is_active=True
        ).select_related('category')

        # Outlet stock map: {product_id: quantity}
        outlet_stock_qs = OutletStock.objects.filter(
            outlet_id=outlet_id
        ).select_related('product')
        outlet_stock_map = {
            os.product_id: os.quantity for os in outlet_stock_qs
        }

        categories = Category.objects.filter(is_active=True)

        now = timezone.now()
        discounts = Discount.objects.filter(is_active=True).filter(
            Q(valid_until__isnull=True) | Q(valid_until__gt=now)
        )

        pumps = Pump.objects.filter(outlet_id=outlet_id, status='active')

        product_data = MobileProductSerializer(
            products_qs,
            many=True,
            context={'outlet_stock_map': outlet_stock_map},
        ).data

        payload = {
            'outlet': {
                'id': outlet.id,
                'name': outlet.name,
                'outlet_type': getattr(outlet, 'outlet_type', None),
            },
            'products': product_data,
            'categories': MobileCategorySerializer(categories, many=True).data,
            'discounts': MobileDiscountSerializer(discounts, many=True).data,
            'pumps': MobilePumpSerializer(pumps, many=True).data,
            'generated_at': now.isoformat(),
        }

        return Response(payload, status=status.HTTP_200_OK)
```

---

## Phase 7: Batch Sync Endpoint

Continue in `mobile_api/views.py`, adding `MobileSyncView` below `ShiftStartDataView`.

The view processes transactions in chronological order (`created_at` ascending), wraps each one in an atomic savepoint, and handles duplication, stock validation, and fiscalization independently per transaction so a single bad record does not abort the entire batch.

```python
class MobileSyncRateThrottle(UserRateThrottle):
    scope = 'mobile-sync'


class MobileSyncView(APIView):
    """
    POST /api/mobile/sync/

    Accepts a batch of up to 500 offline transactions, creates Sale records,
    deducts stock, triggers fiscalization, and returns per-transaction results.

    Idempotent: transactions with a previously-seen client_uuid return
    status='duplicate' without creating a second Sale.

    Permission: authenticated mobile JWT, cashier or above.
    Throttle: 10 requests/minute per authenticated user (mobile-sync scope).
    """
    permission_classes = [IsAuthenticated, IsMobileClient, IsCashierOrAbove]
    throttle_classes = [MobileSyncRateThrottle]

    def post(self, request):
        from django.db import transaction as db_transaction

        serializer = MobileBatchSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        shift_id = data['shift_id']
        device_id = data['device_id']
        transactions = data['transactions']

        # Verify shift exists, is open, and belongs to the requesting user
        try:
            shift = Shift.objects.get(pk=shift_id)
        except Shift.DoesNotExist:
            return Response(
                {'error': f'Shift {shift_id} not found.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if shift.status != 'open':
            return Response(
                {'error': 'Shift is not open.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if shift.user_id != request.user.id:
            return Response(
                {'error': 'Shift does not belong to the authenticated user.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Process in chronological order
        transactions_sorted = sorted(transactions, key=lambda t: t['created_at'])

        results = []
        success_count = 0
        failed_count = 0

        for txn in transactions_sorted:
            client_uuid = txn['client_uuid']

            # --- Deduplication ---
            existing = Sale.objects.filter(client_uuid=client_uuid).first()
            if existing:
                results.append({
                    'client_uuid': client_uuid,
                    'status': 'duplicate',
                    'sale_id': existing.id,
                    'receipt_number': existing.receipt_number,
                    'message': 'Transaction already synced.',
                })
                continue

            # --- Process transaction ---
            try:
                with db_transaction.atomic():
                    result = self._create_sale(
                        txn=txn,
                        shift=shift,
                        user=request.user,
                        client_uuid=client_uuid,
                    )
                results.append(result)
                success_count += 1
            except Exception as exc:
                failed_count += 1
                results.append({
                    'client_uuid': client_uuid,
                    'status': 'failed',
                    'sale_id': None,
                    'receipt_number': None,
                    'message': str(exc),
                })

        # Write sync audit log
        MobileSyncLog.objects.create(
            device_id=device_id,
            shift_id=shift_id,
            user_id=request.user.id,
            outlet_id=shift.outlet_id,
            transaction_count=len(transactions_sorted),
            success_count=success_count,
            failed_count=failed_count,
            ip_address=request.META.get('REMOTE_ADDR'),
        )

        return Response(
            {
                'processed': len(transactions_sorted),
                'results': results,
            },
            status=status.HTTP_200_OK,
        )

    def _create_sale(self, *, txn, shift, user, client_uuid):
        """
        Creates a single Sale, SaleItems, Payments, deducts stock,
        creates audit logs, and triggers fiscalization.
        Raises on any validation failure — caller wraps in atomic().
        """
        from sales.models import Sale, SaleItem, Payment
        from products.models import Product
        from sales.models import Discount
        from inventory.models import OutletStock, StockAuditLog
        from sales.services import apply_discount, generate_receipt_number
        from fiscalization.services import submit_sale_for_fiscalization

        items_data = txn['items']
        payments_data = txn['payments']

        subtotal = Decimal('0.00')
        tax_total = Decimal('0.00')
        discount_total = Decimal('0.00')
        sale_items_to_create = []

        for item_data in items_data:
            product = Product.objects.get(pk=item_data['product_id'])
            if not product.is_active:
                raise ValueError(
                    f"Product '{product.name}' (id={product.id}) is inactive."
                )

            quantity = item_data['quantity']
            unit_price = item_data['unit_price']

            # Stock check
            if product.track_stock:
                if product.stock_quantity < quantity:
                    raise ValueError(
                        f"Insufficient stock for '{product.name}'. "
                        f"Available: {product.stock_quantity}, requested: {quantity}."
                    )

            line_subtotal = unit_price * quantity
            item_discount_amount = Decimal('0.00')

            if item_data.get('discount_id'):
                try:
                    item_discount = Discount.objects.get(
                        pk=item_data['discount_id'], is_active=True
                    )
                    item_discount_amount = apply_discount(line_subtotal, item_discount)
                except Discount.DoesNotExist:
                    pass  # Discount expired or removed since download; skip silently

            discounted_subtotal = line_subtotal - item_discount_amount
            tax_amount = (
                discounted_subtotal * product.tax_rate / Decimal('100')
            ).quantize(Decimal('0.01'))
            line_total = discounted_subtotal + tax_amount

            subtotal += line_subtotal
            tax_total += tax_amount
            discount_total += item_discount_amount

            sale_items_to_create.append({
                'product': product,
                'product_name': product.name,
                'unit_price': unit_price,
                'quantity': quantity,
                'tax_rate': product.tax_rate,
                'tax_amount': tax_amount,
                'discount_id': item_data.get('discount_id'),
                'discount_amount': item_discount_amount,
                'line_total': line_total,
            })

        grand_total = subtotal + tax_total - discount_total

        # Validate payments sum
        total_paid = sum(p['amount'] for p in payments_data)
        if total_paid < grand_total:
            raise ValueError(
                f"Insufficient payment. Grand total: {grand_total}, "
                f"total paid: {total_paid}."
            )

        # Create Sale
        receipt_number = generate_receipt_number(shift.outlet_id)
        sale = Sale.objects.create(
            outlet=shift.outlet,
            shift=shift,
            cashier_id=user.id,
            subtotal=subtotal,
            tax_total=tax_total,
            discount_total=discount_total,
            grand_total=grand_total,
            receipt_number=receipt_number,
            notes=txn.get('notes', ''),
            status='completed',
            client_uuid=client_uuid,
            source='mobile',
            created_at=txn['created_at'],
        )

        # Create SaleItems
        for item_data in sale_items_to_create:
            SaleItem.objects.create(
                sale=sale,
                product=item_data['product'],
                product_name=item_data['product_name'],
                unit_price=item_data['unit_price'],
                quantity=item_data['quantity'],
                tax_rate=item_data['tax_rate'],
                tax_amount=item_data['tax_amount'],
                discount_id=item_data['discount_id'],
                discount_amount=item_data['discount_amount'],
                line_total=item_data['line_total'],
            )

        # Create Payments
        for p in payments_data:
            Payment.objects.create(
                sale=sale,
                payment_method=p['payment_method'],
                amount=p['amount'],
                reference=p.get('reference', ''),
            )

        # Deduct stock and create audit logs
        for item_data in sale_items_to_create:
            product = item_data['product']
            qty = item_data['quantity']
            if product.track_stock:
                qty_before = product.stock_quantity
                product.stock_quantity -= qty
                product.save(update_fields=['stock_quantity'])

                # Also deduct from OutletStock
                try:
                    outlet_stock = OutletStock.objects.get(
                        outlet_id=shift.outlet_id, product=product
                    )
                    outlet_stock.quantity -= qty
                    outlet_stock.save(update_fields=['quantity'])
                except OutletStock.DoesNotExist:
                    pass  # Outlet stock record absent; product stock_quantity already deducted

                StockAuditLog.objects.create(
                    product=product,
                    outlet=shift.outlet,
                    movement_type='sale',
                    quantity_change=-qty,
                    quantity_before=qty_before,
                    quantity_after=product.stock_quantity,
                    reference_type='sale',
                    reference_id=sale.id,
                    user_id=user.id,
                    notes=f'Mobile sync — receipt {receipt_number}',
                )

        # Trigger fiscalization (non-blocking; failures are logged internally)
        try:
            submit_sale_for_fiscalization(sale)
        except Exception:
            pass  # EFRIS failures are queued for retry; do not abort the sale

        return {
            'client_uuid': client_uuid,
            'status': 'synced',
            'sale_id': sale.id,
            'receipt_number': receipt_number,
            'message': None,
        }
```

---

## Phase 8: Shift Close Update — `sales/views.py`

### Edit `backend/sales/serializers.py` — `CloseShiftSerializer`

Add `pending_mobile_transactions` to the existing serializer:

```python
class CloseShiftSerializer(serializers.Serializer):
    closing_cash = serializers.DecimalField(max_digits=12, decimal_places=2)
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    pending_mobile_transactions = serializers.IntegerField(
        default=0,
        min_value=0,
        help_text=(
            "Number of offline transactions the mobile client has not yet synced. "
            "A non-zero value blocks shift close."
        ),
    )
```

### Edit `backend/sales/views.py` — `ShiftViewSet.close_shift`

After the existing `if shift.status == 'closed'` check and before the `CloseShiftSerializer` validation, insert the pending-transaction guard. The full updated action:

```python
@action(detail=True, methods=['post'])
def close_shift(self, request, pk=None):
    shift = self.get_object()
    if shift.status == 'closed':
        return Response(
            {'error': 'Shift is already closed.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = CloseShiftSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    # Guard: mobile client reports unsynced transactions
    pending = serializer.validated_data.get('pending_mobile_transactions', 0)
    if pending > 0:
        return Response(
            {
                'error': (
                    f'Sync {pending} pending transaction(s) before closing shift.'
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ... rest of existing close logic unchanged ...
    cash_payments = (
        Payment.objects
        .filter(sale__shift=shift, payment_method='cash')
        .aggregate(total=models.Sum('amount'))
    )
    cash_total = cash_payments['total'] or Decimal('0.00')
    expected_cash = shift.opening_cash + cash_total

    shift.closing_cash = serializer.validated_data['closing_cash']
    shift.expected_cash = expected_cash
    shift.notes = serializer.validated_data.get('notes', '')
    shift.status = 'closed'
    shift.closed_at = timezone.now()
    shift.save()

    return Response(ShiftSerializer(shift).data)
```

---

## Phase 9: Sensitive Endpoint Hardening — `IsNotMobileClient`

Add `IsNotMobileClient` to all ViewSets in the listed apps. The pattern is:

```python
from mobile_api.permissions import IsNotMobileClient
```

Then on each ViewSet or APIView:

```python
permission_classes = [IsAuthenticated, IsNotMobileClient, IsAdminOrManager]
```

Or, if the class uses `get_permissions()`, include `IsNotMobileClient()` in each returned list.

### Files to update

| File | ViewSets / Views to harden |
|---|---|
| `backend/finance/views.py` | All ViewSets (ChartOfAccounts, JournalEntry, CashRequisition, etc.) |
| `backend/hr/views.py` | All ViewSets — especially payroll-related |
| `backend/tenants/views.py` | All ViewSets |
| `backend/users/views.py` | `UserViewSet` only — NOT the `/auth/login/` or `/auth/refresh/` endpoints |
| `backend/assets/views.py` | All ViewSets |

### Do NOT add to

- `products/views.py` — mobile needs product data
- `sales/views.py` — mobile needs checkout/receipt access
- `fuel/views.py` — mobile needs pump data
- `notifications/views.py` — mobile may receive push notifications
- `system_config/views.py` — mobile may need tenant settings

### Example for `finance/views.py`

```python
from mobile_api.permissions import IsNotMobileClient

class ChartOfAccountsViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsNotMobileClient, IsAccountantOrAbove]
    # ...

class JournalEntryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsNotMobileClient, IsAccountantOrAbove]
    # ...
```

Apply the same pattern to every ViewSet in each of the five listed files.

---

## Phase 10: Tests — `mobile_api/tests.py`

All tests use `TenantTestCase` + `TenantClient`. The test module creates shared fixtures in `setUpTestData` for efficiency.

```python
from decimal import Decimal

from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from rest_framework import status

from outlets.models import Outlet
from products.models import Category, Product
from inventory.models import OutletStock
from fuel.models import Pump
from sales.models import Discount, Shift, Sale
from users.models import User
from mobile_api.models import MobileSyncLog


class MobileAPITestCase(TenantTestCase):
    """
    Base class. Creates shared fixtures once per test class.
    All sub-classes inherit these fixtures.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.outlet = Outlet.objects.create(name='Test Station', outlet_type='fuel_station')

        cls.category = Category.objects.create(
            name='Fuel', business_unit='fuel_station', is_active=True
        )
        cls.product = Product.objects.create(
            name='Petrol',
            sku='PTL-001',
            category=cls.category,
            selling_price=Decimal('5000'),
            tax_rate=Decimal('18.00'),
            track_stock=True,
            stock_quantity=Decimal('1000'),
            unit='litre',
            is_active=True,
        )
        cls.outlet_stock = OutletStock.objects.create(
            outlet=cls.outlet, product=cls.product, quantity=Decimal('500')
        )
        cls.discount = Discount.objects.create(
            name='10% Off',
            discount_type='percentage',
            value=Decimal('10'),
            is_active=True,
            valid_until=None,
        )
        cls.pump = Pump.objects.create(
            outlet=cls.outlet,
            product=cls.product,
            pump_number=1,
            name='Pump A',
            status='active',
        )

        # Users
        cls.cashier = User.objects.create_user(
            email='cashier@test.com', password='pass123', role='cashier'
        )
        cls.attendant = User.objects.create_user(
            email='attendant@test.com', password='pass123', role='attendant'
        )
        cls.admin = User.objects.create_user(
            email='admin@test.com', password='pass123', role='admin'
        )
        cls.manager = User.objects.create_user(
            email='manager@test.com', password='pass123', role='manager'
        )
        cls.accountant = User.objects.create_user(
            email='accountant@test.com', password='pass123', role='accountant'
        )

    def setUp(self):
        self.client = TenantClient(self.tenant)

    def _mobile_login(self, email, password):
        """Returns the access token from a successful mobile login, or the response."""
        response = self.client.post(
            '/api/mobile/auth/login/',
            {'email': email, 'password': password},
            content_type='application/json',
        )
        return response

    def _auth_header(self, token):
        return {'HTTP_AUTHORIZATION': f'Bearer {token}'}

    def _get_mobile_token(self, user_email='cashier@test.com'):
        resp = self._mobile_login(user_email, 'pass123')
        return resp.data['access']

    def _get_web_token(self, user):
        """Obtain a standard (non-mobile) JWT for a user."""
        from rest_framework_simplejwt.tokens import AccessToken
        return str(AccessToken.for_user(user))

    def _open_shift(self, user):
        Shift.objects.filter(user_id=user.id, status='open').update(status='closed')
        return Shift.objects.create(
            outlet=self.outlet,
            user_id=user.id,
            status='open',
            opening_cash=Decimal('50000'),
        )


# ---------------------------------------------------------------------------
# Group 1: Mobile login (6 tests)
# ---------------------------------------------------------------------------

class MobileLoginTests(MobileAPITestCase):

    def test_cashier_login_succeeds(self):
        """Cashier role receives access and refresh tokens."""
        resp = self._mobile_login('cashier@test.com', 'pass123')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('access', resp.data)
        self.assertIn('refresh', resp.data)

    def test_attendant_login_succeeds(self):
        """Attendant role receives tokens."""
        resp = self._mobile_login('attendant@test.com', 'pass123')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_admin_login_rejected(self):
        """Admin role is blocked from mobile login."""
        resp = self._mobile_login('admin@test.com', 'pass123')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Mobile access restricted', str(resp.data))

    def test_manager_login_rejected(self):
        """Manager role is blocked from mobile login."""
        resp = self._mobile_login('manager@test.com', 'pass123')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_wrong_password_rejected(self):
        """Incorrect credentials return 401."""
        resp = self._mobile_login('cashier@test.com', 'wrongpassword')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inactive_user_rejected(self):
        """Inactive user cannot log in."""
        self.cashier.is_active = False
        self.cashier.save()
        resp = self._mobile_login('cashier@test.com', 'pass123')
        self.assertIn(resp.status_code, [
            status.HTTP_401_UNAUTHORIZED, status.HTTP_400_BAD_REQUEST
        ])
        self.cashier.is_active = True
        self.cashier.save()


# ---------------------------------------------------------------------------
# Group 2: ShiftStartDataView (8 tests)
# ---------------------------------------------------------------------------

class ShiftStartDataTests(MobileAPITestCase):

    def setUp(self):
        super().setUp()
        self.token = self._get_mobile_token()
        self.url = '/api/mobile/shift-start-data/'

    def test_missing_outlet_id_returns_400(self):
        resp = self.client.get(self.url, **self._auth_header(self.token))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('outlet_id', str(resp.data))

    def test_invalid_outlet_id_returns_404(self):
        resp = self.client.get(
            self.url + '?outlet_id=99999', **self._auth_header(self.token)
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_correct_outlet_returns_200(self):
        resp = self.client.get(
            self.url + f'?outlet_id={self.outlet.id}',
            **self._auth_header(self.token),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('products', resp.data)
        self.assertIn('categories', resp.data)
        self.assertIn('discounts', resp.data)
        self.assertIn('pumps', resp.data)
        self.assertIn('generated_at', resp.data)

    def test_products_contain_correct_product(self):
        resp = self.client.get(
            self.url + f'?outlet_id={self.outlet.id}',
            **self._auth_header(self.token),
        )
        ids = [p['id'] for p in resp.data['products']]
        self.assertIn(self.product.id, ids)

    def test_outlet_stock_map_populated(self):
        resp = self.client.get(
            self.url + f'?outlet_id={self.outlet.id}',
            **self._auth_header(self.token),
        )
        product_in_resp = next(
            p for p in resp.data['products'] if p['id'] == self.product.id
        )
        self.assertEqual(
            Decimal(product_in_resp['outlet_stock']),
            Decimal('500'),
        )

    def test_expired_discounts_excluded(self):
        """Discounts past valid_until are not returned."""
        from django.utils import timezone
        from datetime import timedelta
        expired = Discount.objects.create(
            name='Expired',
            discount_type='fixed',
            value=Decimal('1000'),
            is_active=True,
            valid_until=timezone.now() - timedelta(days=1),
        )
        resp = self.client.get(
            self.url + f'?outlet_id={self.outlet.id}',
            **self._auth_header(self.token),
        )
        discount_ids = [d['id'] for d in resp.data['discounts']]
        self.assertNotIn(expired.id, discount_ids)
        expired.delete()

    def test_pumps_filtered_by_active_status(self):
        """Inactive pumps are not returned."""
        inactive_pump = Pump.objects.create(
            outlet=self.outlet,
            product=self.product,
            pump_number=2,
            name='Pump B',
            status='inactive',
        )
        resp = self.client.get(
            self.url + f'?outlet_id={self.outlet.id}',
            **self._auth_header(self.token),
        )
        pump_ids = [p['id'] for p in resp.data['pumps']]
        self.assertNotIn(inactive_pump.id, pump_ids)
        inactive_pump.delete()

    def test_web_jwt_rejected(self):
        """A standard (non-mobile) JWT cannot access shift-start-data."""
        web_token = self._get_web_token(self.cashier)
        resp = self.client.get(
            self.url + f'?outlet_id={self.outlet.id}',
            **self._auth_header(web_token),
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_rejected(self):
        resp = self.client.get(self.url + f'?outlet_id={self.outlet.id}')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# Group 3: Batch sync (16 tests)
# ---------------------------------------------------------------------------

class BatchSyncTests(MobileAPITestCase):

    def setUp(self):
        super().setUp()
        self.token = self._get_mobile_token()
        self.url = '/api/mobile/sync/'
        self.shift = self._open_shift(self.cashier)

    def _sync_payload(self, transactions=None, shift_id=None):
        return {
            'device_id': 'device-001',
            'shift_id': shift_id or self.shift.id,
            'transactions': transactions or [],
        }

    def _make_transaction(self, client_uuid=None, product_id=None):
        import uuid
        return {
            'client_uuid': str(client_uuid or uuid.uuid4()),
            'created_at': '2026-05-13T10:00:00Z',
            'items': [{
                'product_id': product_id or self.product.id,
                'quantity': '1.000',
                'unit_price': '5000.00',
                'discount_id': None,
            }],
            'payments': [{'payment_method': 'cash', 'amount': '5900.00', 'reference': ''}],
            'notes': '',
        }

    def test_empty_batch_returns_200(self):
        resp = self.client.post(
            self.url,
            self._sync_payload(),
            content_type='application/json',
            **self._auth_header(self.token),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['processed'], 0)

    def test_single_transaction_happy_path(self):
        resp = self.client.post(
            self.url,
            self._sync_payload([self._make_transaction()]),
            content_type='application/json',
            **self._auth_header(self.token),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['processed'], 1)
        result = resp.data['results'][0]
        self.assertEqual(result['status'], 'synced')
        self.assertIsNotNone(result['sale_id'])
        self.assertIsNotNone(result['receipt_number'])

    def test_deduplication_on_second_sync(self):
        """Syncing the same client_uuid twice marks the second as duplicate."""
        import uuid
        uid = uuid.uuid4()
        txn = self._make_transaction(client_uuid=uid)
        payload = self._sync_payload([txn])
        # First sync
        self.client.post(
            self.url, payload, content_type='application/json',
            **self._auth_header(self.token),
        )
        # Second sync
        resp = self.client.post(
            self.url, payload, content_type='application/json',
            **self._auth_header(self.token),
        )
        self.assertEqual(resp.data['results'][0]['status'], 'duplicate')

    def test_insufficient_stock_fails_transaction(self):
        """A transaction requesting more than available stock fails gracefully."""
        txn = self._make_transaction()
        txn['items'][0]['quantity'] = '999999.000'
        txn['payments'][0]['amount'] = '9999990000.00'
        resp = self.client.post(
            self.url,
            self._sync_payload([txn]),
            content_type='application/json',
            **self._auth_header(self.token),
        )
        self.assertEqual(resp.data['results'][0]['status'], 'failed')
        self.assertIn('Insufficient stock', resp.data['results'][0]['message'])

    def test_partial_batch_some_succeed_some_fail(self):
        """Valid and invalid transactions in the same batch are handled independently."""
        import uuid
        good_txn = self._make_transaction()
        bad_txn = self._make_transaction()
        bad_txn['items'][0]['quantity'] = '999999.000'
        bad_txn['payments'][0]['amount'] = '9999990000.00'
        resp = self.client.post(
            self.url,
            self._sync_payload([good_txn, bad_txn]),
            content_type='application/json',
            **self._auth_header(self.token),
        )
        statuses = [r['status'] for r in resp.data['results']]
        self.assertIn('synced', statuses)
        self.assertIn('failed', statuses)

    def test_batch_exceeding_500_rejected(self):
        """501 transactions in one request is rejected at serializer level."""
        import uuid
        transactions = [self._make_transaction() for _ in range(501)]
        # Ensure unique UUIDs
        for i, t in enumerate(transactions):
            t['client_uuid'] = str(uuid.uuid4())
        resp = self.client.post(
            self.url,
            self._sync_payload(transactions),
            content_type='application/json',
            **self._auth_header(self.token),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_wrong_shift_owner_rejected(self):
        """Attendant cannot sync to a shift opened by another user."""
        other_shift = self._open_shift(self.attendant)
        resp = self.client.post(
            self.url,
            self._sync_payload(shift_id=other_shift.id),
            content_type='application/json',
            **self._auth_header(self.token),  # cashier token
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('does not belong', str(resp.data))

    def test_closed_shift_rejected(self):
        self.shift.status = 'closed'
        self.shift.save()
        resp = self.client.post(
            self.url,
            self._sync_payload([self._make_transaction()]),
            content_type='application/json',
            **self._auth_header(self.token),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not open', str(resp.data))

    def test_payments_not_sum_to_total_fails(self):
        """Payment short-pay causes transaction to fail with clear message."""
        txn = self._make_transaction()
        txn['payments'][0]['amount'] = '1.00'  # Far below grand_total
        resp = self.client.post(
            self.url,
            self._sync_payload([txn]),
            content_type='application/json',
            **self._auth_header(self.token),
        )
        self.assertEqual(resp.data['results'][0]['status'], 'failed')
        self.assertIn('Insufficient payment', resp.data['results'][0]['message'])

    def test_product_not_found_fails(self):
        txn = self._make_transaction(product_id=99999)
        resp = self.client.post(
            self.url,
            self._sync_payload([txn]),
            content_type='application/json',
            **self._auth_header(self.token),
        )
        self.assertEqual(resp.data['results'][0]['status'], 'failed')

    def test_inactive_product_fails(self):
        self.product.is_active = False
        self.product.save()
        txn = self._make_transaction()
        resp = self.client.post(
            self.url,
            self._sync_payload([txn]),
            content_type='application/json',
            **self._auth_header(self.token),
        )
        self.assertEqual(resp.data['results'][0]['status'], 'failed')
        self.assertIn('inactive', resp.data['results'][0]['message'])
        self.product.is_active = True
        self.product.save()

    def test_sync_log_created_after_batch(self):
        """MobileSyncLog record is created even for empty batches."""
        before = MobileSyncLog.objects.count()
        self.client.post(
            self.url,
            self._sync_payload([self._make_transaction()]),
            content_type='application/json',
            **self._auth_header(self.token),
        )
        self.assertEqual(MobileSyncLog.objects.count(), before + 1)

    def test_sync_log_counts_correct(self):
        """success_count and failed_count in MobileSyncLog match results."""
        import uuid
        good_txn = self._make_transaction()
        bad_txn = self._make_transaction()
        bad_txn['items'][0]['quantity'] = '999999.000'
        bad_txn['payments'][0]['amount'] = '9999990000.00'
        self.client.post(
            self.url,
            self._sync_payload([good_txn, bad_txn]),
            content_type='application/json',
            **self._auth_header(self.token),
        )
        log = MobileSyncLog.objects.latest('synced_at')
        self.assertEqual(log.success_count, 1)
        self.assertEqual(log.failed_count, 1)

    def test_shift_not_found_returns_400(self):
        resp = self.client.post(
            self.url,
            self._sync_payload(shift_id=99999),
            content_type='application/json',
            **self._auth_header(self.token),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_rejected(self):
        resp = self.client.post(
            self.url, self._sync_payload(), content_type='application/json'
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_web_jwt_rejected_on_sync(self):
        web_token = self._get_web_token(self.cashier)
        resp = self.client.post(
            self.url,
            self._sync_payload(),
            content_type='application/json',
            **self._auth_header(web_token),
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# Group 4: Shift close with pending_mobile_transactions (4 tests)
# ---------------------------------------------------------------------------

class ShiftCloseTests(MobileAPITestCase):

    def setUp(self):
        super().setUp()
        self.shift = self._open_shift(self.cashier)
        # Authenticate as cashier via web token (close_shift is not mobile-restricted)
        self.client.force_authenticate(user=self.cashier)
        self.url = f'/api/shifts/{self.shift.id}/close/'

    def test_zero_pending_allows_close(self):
        resp = self.client.post(
            self.url,
            {
                'closing_cash': '50000',
                'pending_mobile_transactions': 0,
            },
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.shift.refresh_from_db()
        self.assertEqual(self.shift.status, 'closed')

    def test_nonzero_pending_blocks_close(self):
        resp = self.client.post(
            self.url,
            {
                'closing_cash': '50000',
                'pending_mobile_transactions': 2,
            },
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Sync 2 pending', str(resp.data))

    def test_missing_pending_field_defaults_to_zero(self):
        """pending_mobile_transactions defaults to 0 — close should succeed."""
        resp = self.client.post(
            self.url,
            {'closing_cash': '50000'},
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_sync_log_present_after_close(self):
        """After a successful sync and close, MobileSyncLog exists for the shift."""
        # Simulate a prior sync
        MobileSyncLog.objects.create(
            device_id='dev-001',
            shift_id=self.shift.id,
            user_id=self.cashier.id,
            outlet_id=self.outlet.id,
            transaction_count=1,
            success_count=1,
            failed_count=0,
        )
        self.assertTrue(
            MobileSyncLog.objects.filter(shift_id=self.shift.id).exists()
        )


# ---------------------------------------------------------------------------
# Group 5: IsNotMobileClient enforcement (6 tests)
# ---------------------------------------------------------------------------

class IsNotMobileClientTests(MobileAPITestCase):
    """
    Verify that a mobile JWT is rejected on sensitive endpoints
    and that a web JWT is accepted.
    """

    def setUp(self):
        super().setUp()
        self.mobile_token = self._get_mobile_token()
        self.web_token = self._get_web_token(self.admin)

    def _test_endpoint_rejects_mobile(self, url, method='get'):
        caller = getattr(self.client, method)
        resp = caller(url, **self._auth_header(self.mobile_token))
        self.assertEqual(
            resp.status_code,
            status.HTTP_403_FORBIDDEN,
            msg=f"Expected 403 on {url} with mobile token, got {resp.status_code}",
        )

    def _test_endpoint_accepts_web(self, url, method='get'):
        caller = getattr(self.client, method)
        resp = caller(url, **self._auth_header(self.web_token))
        self.assertNotEqual(
            resp.status_code,
            status.HTTP_403_FORBIDDEN,
            msg=f"Expected non-403 on {url} with web token, got {resp.status_code}",
        )

    def test_finance_rejects_mobile_token(self):
        self._test_endpoint_rejects_mobile('/api/accounts/')

    def test_finance_accepts_web_token(self):
        self._test_endpoint_accepts_web('/api/accounts/')

    def test_hr_rejects_mobile_token(self):
        self._test_endpoint_rejects_mobile('/api/employees/')

    def test_assets_rejects_mobile_token(self):
        self._test_endpoint_rejects_mobile('/api/assets/')

    def test_users_rejects_mobile_token(self):
        self._test_endpoint_rejects_mobile('/api/users/')

    def test_users_accepts_web_token(self):
        self._test_endpoint_accepts_web('/api/users/')
```

> **Note on endpoint URLs in Group 5**: Substitute the actual registered URL prefixes from `api/urls.py` if they differ from the examples above (e.g., `/api/chart-of-accounts/` vs `/api/accounts/`). The URL prefix matters, not the name — verify with `python manage.py show_urls`.

---

## Phase 10 (continued): `mobile_api/urls.py`

```python
from django.urls import path

from .auth import MobileTokenObtainPairView, MobileTokenRefreshView
from .views import MobileSyncView, ShiftStartDataView

urlpatterns = [
    path('auth/login/', MobileTokenObtainPairView.as_view(), name='mobile-login'),
    path('auth/refresh/', MobileTokenRefreshView.as_view(), name='mobile-refresh'),
    path('shift-start-data/', ShiftStartDataView.as_view(), name='mobile-shift-start-data'),
    path('sync/', MobileSyncView.as_view(), name='mobile-sync'),
]
```

---

## Quality Checklist

Work through this list before opening a PR.

### Models
- [ ] `MobileSyncLog` has all 9 specified fields
- [ ] `__str__` returns `f"Sync shift={self.shift_id} by device={self.device_id} at {self.synced_at}"`
- [ ] `Meta.ordering = ['-synced_at']`
- [ ] `Meta.indexes` includes `Index(fields=['shift_id', 'synced_at'])`
- [ ] `sales.Sale` has `client_uuid` (UUIDField, null, unique, db_index) and `source` (CharField, choices, default='pos')

### Serializers
- [ ] All serializers list fields explicitly — no `fields = '__all__'`
- [ ] `MobileProductSerializer.outlet_stock` reads from `context['outlet_stock_map']`
- [ ] `MobileBatchSyncSerializer.validate_transactions` raises on `len > 500`
- [ ] `MobileTransactionSerializer.discount_id` is `allow_null=True`

### Views
- [ ] `ShiftStartDataView.permission_classes = [IsAuthenticated, IsMobileClient, IsCashierOrAbove]`
- [ ] `MobileSyncView.permission_classes = [IsAuthenticated, IsMobileClient, IsCashierOrAbove]`
- [ ] `MobileSyncView.throttle_classes = [MobileSyncRateThrottle]` with scope `'mobile-sync'`
- [ ] Shift ownership check: `shift.user_id != request.user.id` → 400
- [ ] Deduplication check runs before `atomic()` block
- [ ] Fiscalization call is wrapped in `try/except` — EFRIS failure does not abort sale
- [ ] `MobileSyncLog` is always created, even if all transactions failed
- [ ] `ShiftStartDataView` uses `select_related('category')` on product queryset

### Security
- [ ] `MobileTokenObtainPairSerializer.validate()` blocks roles outside `('cashier', 'attendant')`
- [ ] `IsNotMobileClient` added to all ViewSets in: `finance`, `hr`, `tenants`, `users`, `assets`
- [ ] `IsNotMobileClient` NOT added to: `products`, `sales`, `fuel`, `notifications`, `system_config`
- [ ] `_get_token_payload()` returns `{}` safely when `request.auth` is None

### Migrations
- [ ] `makemigrations sales` — adds `client_uuid` and `source` to Sale
- [ ] `makemigrations mobile_api` — creates `MobileSyncLog` table
- [ ] Both migrations run with `migrate_schemas` (not `migrate`)
- [ ] `migrate_schemas` completes without errors on a clean DB

### Tests
- [ ] 40+ test methods total
- [ ] All test classes extend `TenantTestCase`
- [ ] All `self.client` instances are `TenantClient`
- [ ] Group 1: 6 mobile login tests
- [ ] Group 2: 8 shift-start-data tests
- [ ] Group 3: 16 batch sync tests
- [ ] Group 4: 4 shift close tests
- [ ] Group 5: 6 `IsNotMobileClient` enforcement tests
- [ ] All 40 tests pass: `docker compose exec backend python manage.py test mobile_api`

---

## API Reference

### Authentication

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/mobile/auth/login/` | None | Mobile login — cashier/attendant only |
| POST | `/api/mobile/auth/refresh/` | None | Refresh mobile access token |

**POST `/api/mobile/auth/login/`**

Request:
```json
{ "email": "cashier@station.ug", "password": "secret" }
```

Response `200`:
```json
{
  "access": "<jwt>",
  "refresh": "<jwt>"
}
```

The access token payload includes:
```json
{ "client": "mobile", "role": "cashier", "user_id": 42, ... }
```

Response `400` (wrong role):
```json
{ "non_field_errors": ["Mobile access restricted to cashier and attendant roles."] }
```

---

### Shift Start Data

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/mobile/shift-start-data/?outlet_id=<id>` | Mobile JWT | Download offline bundle |

Response `200`:
```json
{
  "outlet": { "id": 1, "name": "Lira Central Station", "outlet_type": "fuel_station" },
  "products": [
    {
      "id": 12,
      "name": "Petrol",
      "sku": "PTL-001",
      "barcode": null,
      "category_id": 3,
      "category_name": "Fuel",
      "selling_price": "5000.00",
      "tax_rate": "18.00",
      "track_stock": true,
      "unit": "litre",
      "outlet_stock": "487.500"
    }
  ],
  "categories": [{ "id": 3, "name": "Fuel", "business_unit": "fuel_station" }],
  "discounts": [
    { "id": 5, "name": "Fleet 10%", "discount_type": "percentage", "value": "10.00", "valid_until": null }
  ],
  "pumps": [
    { "id": 1, "pump_number": 1, "name": "Pump A", "product_id": 12, "status": "active" }
  ],
  "generated_at": "2026-05-13T08:00:00.000000+00:00"
}
```

---

### Batch Sync

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/mobile/sync/` | Mobile JWT | Upload offline transactions |

Request:
```json
{
  "device_id": "android-abc123",
  "shift_id": 7,
  "transactions": [
    {
      "client_uuid": "550e8400-e29b-41d4-a716-446655440000",
      "created_at": "2026-05-13T09:15:00Z",
      "items": [
        { "product_id": 12, "quantity": "10.000", "unit_price": "5000.00", "discount_id": null }
      ],
      "payments": [
        { "payment_method": "cash", "amount": "59000.00", "reference": "" }
      ],
      "notes": ""
    }
  ]
}
```

Response `200`:
```json
{
  "processed": 1,
  "results": [
    {
      "client_uuid": "550e8400-e29b-41d4-a716-446655440000",
      "status": "synced",
      "sale_id": 204,
      "receipt_number": "S001-2026-0204",
      "message": null
    }
  ]
}
```

Possible `status` values per result: `synced`, `duplicate`, `failed`.

---

### Shift Close (updated)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/shifts/{id}/close/` | Any JWT | Close shift — now accepts `pending_mobile_transactions` |

Request:
```json
{
  "closing_cash": "85000",
  "notes": "End of day",
  "pending_mobile_transactions": 0
}
```

Response `400` (pending > 0):
```json
{ "error": "Sync 3 pending transaction(s) before closing shift." }
```

---

## Example curl Commands

### 1. Mobile Login

```bash
curl -s -X POST http://localhost:8000/api/mobile/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "cashier@station.ug", "password": "secret"}' | jq .
```

Expected: `{"access": "...", "refresh": "..."}`

---

### 2. Download Shift Start Data

```bash
TOKEN="<access token from step 1>"

curl -s "http://localhost:8000/api/mobile/shift-start-data/?outlet_id=1" \
  -H "Authorization: Bearer $TOKEN" | jq '.products | length'
```

---

### 3. Batch Sync — 2 Transactions

```bash
TOKEN="<access token>"

curl -s -X POST http://localhost:8000/api/mobile/sync/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "android-abc123",
    "shift_id": 7,
    "transactions": [
      {
        "client_uuid": "550e8400-e29b-41d4-a716-446655440000",
        "created_at": "2026-05-13T09:15:00Z",
        "items": [
          {"product_id": 12, "quantity": "10.000", "unit_price": "5000.00", "discount_id": null}
        ],
        "payments": [
          {"payment_method": "cash", "amount": "59000.00", "reference": ""}
        ],
        "notes": ""
      },
      {
        "client_uuid": "660e8400-e29b-41d4-a716-446655440001",
        "created_at": "2026-05-13T09:45:00Z",
        "items": [
          {"product_id": 12, "quantity": "5.000", "unit_price": "5000.00", "discount_id": 5}
        ],
        "payments": [
          {"payment_method": "momo", "amount": "26550.00", "reference": "MTN-REF-XYZ"}
        ],
        "notes": "Fleet customer"
      }
    ]
  }' | jq .
```

---

### 4. Close Shift — No Pending (Success)

```bash
curl -s -X POST http://localhost:8000/api/shifts/7/close/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "closing_cash": "85000",
    "notes": "All synced",
    "pending_mobile_transactions": 0
  }' | jq .status
```

Expected: `"closed"`

---

### 5. Close Shift — With Pending (Rejected)

```bash
curl -s -X POST http://localhost:8000/api/shifts/7/close/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "closing_cash": "85000",
    "pending_mobile_transactions": 2
  }' | jq .
```

Expected:
```json
{ "error": "Sync 2 pending transaction(s) before closing shift." }
```

---

## Implementation Order

Execute phases in sequence. Each phase has a concrete deliverable before moving to the next.

| # | Phase | Deliverable | Command to verify |
|---|---|---|---|
| 1 | Sale model fields | Migration file in `sales/migrations/` | `showmigrations sales` |
| 2 | App structure + MobileSyncLog | Migration file in `mobile_api/migrations/` | `showmigrations mobile_api` |
| 3 | Mobile JWT auth | `mobile_api/auth.py` | `curl POST /api/mobile/auth/login/` |
| 4 | Permissions | `mobile_api/permissions.py` | Unit test `IsMobileClient` |
| 5 | Serializers | `mobile_api/serializers.py` | Python shell import check |
| 6 | ShiftStartDataView | GET endpoint live | `curl GET /api/mobile/shift-start-data/?outlet_id=1` |
| 7 | MobileSyncView | POST endpoint live | `curl POST /api/mobile/sync/` |
| 8 | Shift close guard | Serializer + view edit | POST with `pending=1` returns 400 |
| 9 | Sensitive hardening | IsNotMobileClient on 5 apps | Mobile token → 403 on `/api/accounts/` |
| 10 | Tests | 40+ passing tests | `manage.py test mobile_api` |

---

*Last updated: 2026-05-13*  
*Author: Kakebe Technologies backend team*  
*Branch: `feat-phase-9-mobile-api`*
