# Phase 11 — Inventory Enhancements: Batch / Expiry Tracking & Product Bundles

**Branch**: `feat-phase-11-inventory-enhancements`  
**Depends on**: Phases 1–9 merged to `main`  
**Scope**: Backend only. No new apps — extends `inventory` (ProductBatch model, FIFO deduction, expiry reporting) and `products` (Bundle, BundleItem models, bundle checkout). One new field on `sales.SaleItem`.

---

## Overview

Two proposal gaps are closed in this phase:

1. **Sub-feature A — Product Batch / Expiry Tracking** (proposal §8 Inventory): General-purpose batch records that carry expiry dates and cost prices per receiving event. On checkout, stock is deducted FIFO (earliest expiry first). An `expiring-soon` endpoint surfaces batches approaching expiry so managers can act before write-off.

2. **Sub-feature B — Product Bundles** (proposal §11 Supermarket / Boutique / Bridal): A `Bundle` is a named set of products sold as a single SKU at a combined price. At checkout, one bundle line expands into individual `SaleItem` rows — one per component product — each tagged with the originating `bundle_id`. Stock is deducted per component.

**Key constraints carried forward from the existing codebase:**
- Tenant-scoped apps use `TenantTestCase` + `TenantClient` for tests.
- Cross-schema foreign keys are not possible with `django-tenants` — use `IntegerField` for user references only. `ProductBatch` → `products.Product` and `outlets.Outlet` are same-schema FKs and are allowed. `Bundle` and `BundleItem` live in `products` (already TENANT_APPS).
- `SaleItem.bundle_id` is an `IntegerField` (nullable), not a FK — avoids coupling `sales` to `products` internals.
- Always run `migrate_schemas`, never `migrate`.
- UGX has no fractional subdivision — all new price fields use `decimal_places=0`.
- FIFO batch deduction uses `select_for_update()` inside `transaction.atomic()` to prevent race conditions.
- `INSTALLED_APPS` ordering must be preserved for `django-tenants` — do not sort or deduplicate.

---

## App Registration

No new apps are introduced. `inventory` and `products` are already in `TENANT_APPS`. The only `settings.py` change needed is confirming `inventory` and `products` are present — no edit required unless they were accidentally removed.

No new URL namespace is needed: batch endpoints mount under `inventory/`, bundle endpoints under `products/`.

### `backend/api/urls.py`

The inventory and products routers are already wired. After adding the new ViewSets in Phase 2 and Phase 6, register them with the existing routers in their respective `urls.py` files — no changes to `api/urls.py` itself are required.

---

## Phase 1: `ProductBatch` Model + Migration

### Edit `backend/inventory/models.py`

Add the `ProductBatch` class after `StockAuditLog`. It stores one batch per physical receiving event. Non-perishable products leave `expiry_date` null.

```python
import uuid as _uuid


class ProductBatch(models.Model):
    """
    Represents one physical receiving event for a product at an outlet.
    Perishable goods carry an expiry_date; non-perishables leave it null.
    FIFO deduction orders by expiry_date ascending (nulls last).

    Cross-schema FK rule: product and outlet are same-schema FKs (allowed).
    supplier is same-schema FK (allowed). user_id is IntegerField (cross-schema).
    """
    batch_number = models.CharField(
        max_length=50,
        db_index=True,
        help_text=(
            "Auto-generated from UUID prefix on save if left blank, "
            "or manually entered (e.g. supplier lot number)."
        ),
    )
    product = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name='batches',
    )
    outlet = models.ForeignKey(
        Outlet, on_delete=models.PROTECT, related_name='product_batches',
    )
    supplier = models.ForeignKey(
        Supplier, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='batches',
    )
    quantity = models.DecimalField(
        max_digits=10, decimal_places=3,
        help_text="Current remaining quantity in this batch.",
    )
    received_date = models.DateField(
        auto_now_add=True,
        help_text="Date this batch was received. Set automatically.",
    )
    expiry_date = models.DateField(
        null=True, blank=True,
        db_index=True,
        help_text="Null for non-perishable items.",
    )
    cost_price = models.DecimalField(
        max_digits=12, decimal_places=0,
        null=True, blank=True,
        help_text="Unit cost price at time of receiving (UGX, no fractions).",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Set to False when quantity reaches zero or batch is manually closed.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', 'outlet', 'is_active', 'expiry_date']),
        ]

    def __str__(self):
        return f"Batch {self.batch_number} — {self.product.name} @ {self.outlet.name}"

    def save(self, *args, **kwargs):
        if not self.batch_number:
            self.batch_number = f"BT-{_uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
```

> **Why the composite index?** The FIFO deduction query filters on `product`, `outlet`, `is_active=True` and orders by `expiry_date` — this index covers all four columns.

### Run Migration

```bash
docker compose exec backend python manage.py makemigrations inventory
docker compose exec backend python manage.py migrate_schemas
```

Verify:

```bash
docker compose exec backend python manage.py showmigrations inventory
```

---

## Phase 2: `ProductBatch` Serializers + ViewSet + URLs

### `backend/inventory/serializers.py` — add after existing serializers

```python
from .models import ProductBatch


class ProductBatchSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    outlet_name = serializers.CharField(source='outlet.name', read_only=True)
    supplier_name = serializers.CharField(
        source='supplier.name', read_only=True, allow_null=True,
    )

    class Meta:
        model = ProductBatch
        fields = [
            'id',
            'batch_number',
            'product',
            'product_name',
            'outlet',
            'outlet_name',
            'supplier',
            'supplier_name',
            'quantity',
            'received_date',
            'expiry_date',
            'cost_price',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'batch_number', 'received_date', 'created_at', 'updated_at']


class ProductBatchCreateSerializer(serializers.ModelSerializer):
    """
    Write serializer. batch_number is optional — auto-generated on save if blank.
    """
    class Meta:
        model = ProductBatch
        fields = [
            'batch_number',
            'product',
            'outlet',
            'supplier',
            'quantity',
            'expiry_date',
            'cost_price',
        ]

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value
```

### `backend/inventory/views.py` — add `ProductBatchViewSet`

```python
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from .models import ProductBatch
from .serializers import ProductBatchCreateSerializer, ProductBatchSerializer


class ProductBatchViewSet(viewsets.ModelViewSet):
    """
    GET    /api/inventory/batches/             — list (filterable)
    POST   /api/inventory/batches/             — create batch (admin/manager)
    GET    /api/inventory/batches/{id}/        — retrieve
    PATCH  /api/inventory/batches/{id}/        — update (admin/manager)
    DELETE /api/inventory/batches/{id}/        — not exposed (is_active=False instead)
    """
    queryset = ProductBatch.objects.select_related('product', 'outlet', 'supplier')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product', 'outlet', 'supplier', 'is_active']
    search_fields = ['batch_number', 'product__name']
    ordering_fields = ['expiry_date', 'received_date', 'created_at']
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_permissions(self):
        if self.action in ('create', 'partial_update'):
            return [IsAdminOrManager()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'create':
            return ProductBatchCreateSerializer
        return ProductBatchSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        # Support ?expiry_before= and ?expiry_after= date range filters
        expiry_before = self.request.query_params.get('expiry_before')
        expiry_after = self.request.query_params.get('expiry_after')
        if expiry_before:
            qs = qs.filter(expiry_date__lte=expiry_before)
        if expiry_after:
            qs = qs.filter(expiry_date__gte=expiry_after)
        return qs
```

### `backend/inventory/urls.py` — register `ProductBatchViewSet`

Add alongside the existing router registrations:

```python
from rest_framework.routers import DefaultRouter
from .views import (
    SupplierViewSet,
    OutletStockViewSet,
    PurchaseOrderViewSet,
    StockTransferViewSet,
    StockAuditLogViewSet,
    ProductBatchViewSet,          # <-- add
    ExpiringSoonView,              # <-- add (Phase 4)
)

router = DefaultRouter()
router.register(r'suppliers', SupplierViewSet)
router.register(r'outlet-stock', OutletStockViewSet)
router.register(r'purchase-orders', PurchaseOrderViewSet)
router.register(r'transfers', StockTransferViewSet)
router.register(r'audit-log', StockAuditLogViewSet)
router.register(r'batches', ProductBatchViewSet)    # <-- add

urlpatterns = router.urls + [
    path('expiring-soon/', ExpiringSoonView.as_view(), name='expiring-soon'),  # <-- add (Phase 4)
]
```

---

## Phase 3: FIFO Deduction — Update Checkout Service

### Strategy

When a `track_stock=True` product has at least one active `ProductBatch` at the sale outlet, deduct from batches in FIFO order (earliest non-null `expiry_date` first, then null-expiry batches after all dated ones). If no batches exist, fall back to the existing direct `stock_quantity` deduction path — this preserves backward compatibility for products that predate batch tracking.

FIFO deduction is wrapped in `transaction.atomic()` with `select_for_update()` to prevent two concurrent sales from double-consuming the same batch quantity.

### Edit `backend/sales/services.py`

Locate the `process_checkout` function (or the stock-deduction block within it). Add a `_deduct_fifo` helper and call it from the deduction block.

```python
from django.db import transaction


def _deduct_fifo(product, outlet, quantity_needed, sale, user_id):
    """
    Deducts `quantity_needed` from ProductBatch records at the given outlet
    using FIFO (earliest expiry_date first; null-expiry batches last).

    Returns True if batches covered the full deduction, False if batches were
    absent (caller should fall back to direct stock_quantity deduction).

    Raises ValueError if batches exist but total quantity is insufficient.

    Must be called inside an existing transaction.atomic() block.
    """
    from inventory.models import ProductBatch, StockAuditLog

    active_batches = (
        ProductBatch.objects
        .select_for_update()
        .filter(product=product, outlet=outlet, is_active=True, quantity__gt=0)
        .order_by(
            # Dated batches first (nulls_last), then by received_date as tiebreaker
            models.F('expiry_date').asc(nulls_last=True),
            'received_date',
        )
    )

    if not active_batches.exists():
        return False  # No batches — caller uses legacy deduction

    # Verify total available covers the order before touching any batch
    total_available = sum(b.quantity for b in active_batches)
    if total_available < quantity_needed:
        raise ValueError(
            f"Insufficient batch stock for '{product.name}'. "
            f"Available: {total_available}, requested: {quantity_needed}."
        )

    remaining = quantity_needed
    for batch in active_batches:
        if remaining <= 0:
            break
        deduct = min(batch.quantity, remaining)
        batch.quantity -= deduct
        if batch.quantity == 0:
            batch.is_active = False
        batch.save(update_fields=['quantity', 'is_active', 'updated_at'])
        remaining -= deduct

    return True  # Full deduction satisfied from batches


def _deduct_stock(product, outlet, quantity, sale, user_id):
    """
    Unified stock deduction entry point called from process_checkout.
    Tries FIFO batch deduction first; falls back to legacy path if no batches.
    Also updates OutletStock and writes a StockAuditLog entry.
    """
    from inventory.models import OutletStock, StockAuditLog

    qty_before = product.stock_quantity

    with transaction.atomic():
        # Re-fetch product with row lock for the legacy path
        from products.models import Product as Prod
        product = Prod.objects.select_for_update().get(pk=product.pk)
        qty_before = product.stock_quantity

        used_batches = _deduct_fifo(product, outlet, quantity, sale, user_id)

        # Always deduct from product.stock_quantity regardless of path
        product.stock_quantity -= quantity
        product.save(update_fields=['stock_quantity', 'updated_at'])

        # Deduct from OutletStock
        try:
            outlet_stock = OutletStock.objects.select_for_update().get(
                outlet=outlet, product=product
            )
            outlet_stock.quantity -= quantity
            outlet_stock.save(update_fields=['quantity', 'updated_at'])
        except OutletStock.DoesNotExist:
            pass

        StockAuditLog.objects.create(
            product=product,
            outlet=outlet,
            movement_type='sale',
            quantity_change=-quantity,
            quantity_before=qty_before,
            quantity_after=product.stock_quantity,
            reference_type='sale',
            reference_id=sale.id,
            user_id=user_id,
            notes=f'FIFO batch deduction' if used_batches else 'Direct deduction',
        )
```

### Update `process_checkout` call site

In the existing stock deduction loop inside `process_checkout`, replace the inline deduction block:

```python
# BEFORE (existing direct deduction):
if product.track_stock:
    qty_before = product.stock_quantity
    product.stock_quantity -= item.quantity
    product.save(update_fields=['stock_quantity', 'updated_at'])
    # ... OutletStock and StockAuditLog ...

# AFTER (FIFO-aware deduction):
if product.track_stock:
    _deduct_stock(
        product=product,
        outlet=sale.outlet,
        quantity=item.quantity,
        sale=sale,
        user_id=user_id,
    )
```

> **Note**: The mobile sync path in `mobile_api/views.py` (`_create_sale`) also performs stock deduction inline. Update it to call `_deduct_stock` from `sales.services` in the same way once `sales.services` exports the helper.

---

## Phase 4: Expiring-Soon Endpoint

### `backend/inventory/views.py` — add `ExpiringSoonView`

```python
from django.utils import timezone
from datetime import timedelta
from rest_framework.views import APIView


class ExpiringSoonView(APIView):
    """
    GET /api/inventory/expiring-soon/?days=30&outlet_id=<id>

    Returns active batches whose expiry_date falls within `days` days from today.
    Batches with null expiry_date are excluded (non-perishables have no expiry).
    Optional ?outlet_id= filter; omit to see all outlets.

    Permission: authenticated, admin/manager/accountant (read-only reporting endpoint).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        days_param = request.query_params.get('days', '30')
        try:
            days = int(days_param)
            if days < 1 or days > 365:
                raise ValueError()
        except (TypeError, ValueError):
            return Response(
                {'error': 'days must be an integer between 1 and 365.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        today = timezone.now().date()
        threshold = today + timedelta(days=days)

        batches_qs = (
            ProductBatch.objects
            .select_related('product', 'outlet', 'supplier')
            .filter(
                is_active=True,
                expiry_date__isnull=False,
                expiry_date__lte=threshold,
                expiry_date__gte=today,
            )
            .order_by('expiry_date')
        )

        outlet_id = request.query_params.get('outlet_id')
        if outlet_id:
            batches_qs = batches_qs.filter(outlet_id=outlet_id)

        serializer = ProductBatchSerializer(batches_qs, many=True)
        return Response({
            'days': days,
            'threshold_date': str(threshold),
            'count': batches_qs.count(),
            'results': serializer.data,
        })
```

> The URL path `expiring-soon/` is registered in Phase 2's `urls.py` block above.

---

## Phase 5: `Bundle` + `BundleItem` Models + Migrations

### Edit `backend/products/models.py`

Add both classes after the `Product` class.

```python
class Bundle(models.Model):
    """
    A named set of products sold together at a single combined price.
    Lives in the `products` app (TENANT_APPS) so it is schema-isolated per tenant.

    BundleItem records define the composition.
    SaleItem.bundle_id (IntegerField) cross-references Bundle.pk at checkout.
    """
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    selling_price = models.DecimalField(
        max_digits=12, decimal_places=0,
        help_text="Combined selling price of the bundle (UGX, no fractions).",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} (UGX {self.selling_price})"


class BundleItem(models.Model):
    """
    One component product and its quantity within a Bundle.
    """
    bundle = models.ForeignKey(Bundle, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='bundle_items')
    quantity = models.DecimalField(
        max_digits=10, decimal_places=3,
        help_text="Quantity of this product consumed when one bundle unit is sold.",
    )

    class Meta:
        ordering = ['id']
        unique_together = ('bundle', 'product')

    def __str__(self):
        return f"{self.bundle.name} → {self.product.name} × {self.quantity}"
```

### Run Migrations

```bash
docker compose exec backend python manage.py makemigrations products
docker compose exec backend python manage.py migrate_schemas
```

---

## Phase 6: Bundle Serializers + ViewSet + URLs

### `backend/products/serializers.py` — add after existing serializers

```python
from .models import Bundle, BundleItem


class BundleItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)

    class Meta:
        model = BundleItem
        fields = ['id', 'product', 'product_name', 'product_sku', 'quantity']


class BundleItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = BundleItem
        fields = ['product', 'quantity']

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value


class BundleSerializer(serializers.ModelSerializer):
    items = BundleItemSerializer(many=True, read_only=True)

    class Meta:
        model = Bundle
        fields = [
            'id', 'name', 'description', 'selling_price',
            'is_active', 'items', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class BundleCreateSerializer(serializers.ModelSerializer):
    """
    Write serializer. Accepts nested items and creates them atomically.
    Requires at least one item.
    """
    items = BundleItemWriteSerializer(many=True)

    class Meta:
        model = Bundle
        fields = ['name', 'description', 'selling_price', 'is_active', 'items']

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError(
                "A bundle must contain at least one item."
            )
        # Check for duplicate products within the submitted items
        product_ids = [item['product'].id for item in value]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError(
                "Duplicate products are not allowed in a bundle."
            )
        return value

    def create(self, validated_data):
        from django.db import transaction
        items_data = validated_data.pop('items')
        with transaction.atomic():
            bundle = Bundle.objects.create(**validated_data)
            for item_data in items_data:
                BundleItem.objects.create(bundle=bundle, **item_data)
        return bundle
```

### `backend/products/views.py` — add `BundleViewSet`

```python
from rest_framework.decorators import action

from .models import Bundle, BundleItem
from .serializers import BundleSerializer, BundleCreateSerializer
from inventory.models import OutletStock


class BundleViewSet(viewsets.ModelViewSet):
    """
    GET    /api/bundles/                        — list (filterable by is_active)
    POST   /api/bundles/                        — create (admin/manager)
    GET    /api/bundles/{id}/                   — retrieve with items
    PATCH  /api/bundles/{id}/                   — update (admin/manager)
    DELETE /api/bundles/{id}/                   — delete (admin only)
    GET    /api/bundles/{id}/stock-check/?outlet_id=   — component stock check
    """
    queryset = Bundle.objects.prefetch_related('items__product')
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    filterset_fields = ['is_active']
    search_fields = ['name']

    def get_permissions(self):
        if self.action == 'destroy':
            return [IsAdmin()]
        if self.action in ('create', 'update', 'partial_update'):
            return [IsAdminOrManager()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'create':
            return BundleCreateSerializer
        return BundleSerializer

    @action(detail=True, methods=['get'], url_path='stock-check')
    def stock_check(self, request, pk=None):
        """
        GET /api/bundles/{id}/stock-check/?outlet_id=<id>

        Checks whether each component product has sufficient OutletStock
        to fulfil one unit of this bundle at the given outlet.
        Returns per-component stock status and overall 'can_sell' flag.
        """
        bundle = self.get_object()
        outlet_id = request.query_params.get('outlet_id')
        if not outlet_id:
            return Response(
                {'error': 'outlet_id query parameter is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stock_map = {
            os.product_id: os.quantity
            for os in OutletStock.objects.filter(outlet_id=outlet_id)
        }

        results = []
        can_sell = True
        for item in bundle.items.select_related('product'):
            available = stock_map.get(item.product_id, Decimal('0'))
            sufficient = not item.product.track_stock or available >= item.quantity
            if not sufficient:
                can_sell = False
            results.append({
                'product_id': item.product_id,
                'product_name': item.product.name,
                'required': str(item.quantity),
                'available': str(available),
                'sufficient': sufficient,
            })

        return Response({
            'bundle_id': bundle.id,
            'bundle_name': bundle.name,
            'outlet_id': int(outlet_id),
            'can_sell': can_sell,
            'components': results,
        })
```

### `backend/products/urls.py` — register `BundleViewSet`

```python
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, ProductViewSet, BundleViewSet  # <-- add BundleViewSet

router = DefaultRouter()
router.register(r'categories', CategoryViewSet)
router.register(r'products', ProductViewSet)
router.register(r'bundles', BundleViewSet)   # <-- add

urlpatterns = router.urls
```

---

## Phase 7: Bundle Checkout Integration — Extend Checkout Endpoint

### Step 1: Add `bundle_id` to `SaleItem`

#### Edit `backend/sales/models.py`

Add one field to `SaleItem` after `discount_amount`:

```python
class SaleItem(models.Model):
    # ... existing fields unchanged ...
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    # --- Bundle support (Phase 11) ---
    bundle_id = models.IntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "IntegerField (not FK) cross-referencing products.Bundle.pk. "
            "Set for all SaleItems that originated from a bundle checkout line. "
            "Null for standard (non-bundle) items."
        ),
    )
```

#### Run Migration

```bash
docker compose exec backend python manage.py makemigrations sales
docker compose exec backend python manage.py migrate_schemas
```

Verify:

```bash
docker compose exec backend python manage.py showmigrations sales
```

---

### Step 2: Extend `CheckoutSerializer`

#### Edit `backend/sales/serializers.py`

The existing `CheckoutItemSerializer` accepts `product_id` + `quantity` + `unit_price`. Add a mutually exclusive `bundle_id` path:

```python
class CheckoutItemSerializer(serializers.Serializer):
    # Existing fields
    product_id = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.DecimalField(
        max_digits=10, decimal_places=3, required=False, allow_null=True,
    )
    unit_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True,
    )
    discount_id = serializers.IntegerField(required=False, allow_null=True)

    # Bundle path (new — Phase 11)
    bundle_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, data):
        has_product = bool(data.get('product_id'))
        has_bundle = bool(data.get('bundle_id'))
        if has_product and has_bundle:
            raise serializers.ValidationError(
                "Provide either product_id or bundle_id, not both."
            )
        if not has_product and not has_bundle:
            raise serializers.ValidationError(
                "Either product_id or bundle_id is required."
            )
        if has_product and not data.get('quantity'):
            raise serializers.ValidationError(
                "quantity is required when product_id is provided."
            )
        if has_product and not data.get('unit_price'):
            raise serializers.ValidationError(
                "unit_price is required when product_id is provided."
            )
        return data
```

---

### Step 3: Bundle Expansion in `process_checkout`

#### Edit `backend/sales/services.py` — update `process_checkout`

Locate the item-processing loop in `process_checkout`. Before the existing product-lookup logic, insert a bundle expansion step:

```python
from decimal import Decimal
from django.db import transaction


def _expand_bundle_items(bundle_id, outlet):
    """
    Resolves bundle_id to its component products and returns a list of
    item-dict structures identical to what a regular checkout item produces.

    Each returned dict has the same keys as a validated CheckoutItemSerializer
    item: product_id, quantity, unit_price (component's selling_price),
    discount_id (None), plus bundle_id for SaleItem tagging.

    Raises ValueError if the bundle does not exist or is inactive.
    Raises ValueError if any component product is inactive.
    """
    from products.models import Bundle

    try:
        bundle = Bundle.objects.prefetch_related('items__product').get(pk=bundle_id)
    except Bundle.DoesNotExist:
        raise ValueError(f"Bundle id={bundle_id} does not exist.")

    if not bundle.is_active:
        raise ValueError(f"Bundle '{bundle.name}' is inactive.")

    # Distribute bundle selling_price proportionally across components
    # based on each component's own selling_price weight.
    # If all components have zero selling_price, distribute evenly.
    items = list(bundle.items.select_related('product').all())
    if not items:
        raise ValueError(f"Bundle '{bundle.name}' has no items.")

    total_component_price = sum(
        item.product.selling_price * item.quantity for item in items
    )

    expanded = []
    for bundle_item in items:
        product = bundle_item.product
        if not product.is_active:
            raise ValueError(
                f"Bundle component '{product.name}' (id={product.id}) is inactive."
            )

        component_qty = bundle_item.quantity

        # Proportional unit price from bundle selling_price
        if total_component_price > 0:
            proportion = (
                product.selling_price * component_qty / total_component_price
            )
            # Unit price = bundle's proportional share / component quantity
            unit_price = (bundle.selling_price * proportion / component_qty).quantize(
                Decimal('1')  # UGX — round to whole shilling
            )
        else:
            # Fallback: zero price (gift bundles, etc.)
            unit_price = Decimal('0')

        expanded.append({
            'product_id': product.id,
            'quantity': component_qty,
            'unit_price': unit_price,
            'discount_id': None,
            'bundle_id': bundle.id,
        })

    return expanded


def process_checkout(validated_data, user, outlet):
    """
    Processes a checkout request. Expands any bundle_id items into component
    SaleItems before running the standard per-product validation and stock
    deduction loop.
    """
    with transaction.atomic():
        raw_items = validated_data['items']
        payments_data = validated_data['payments']

        # --- Bundle expansion ---
        expanded_items = []
        for raw_item in raw_items:
            if raw_item.get('bundle_id'):
                expanded_items.extend(
                    _expand_bundle_items(raw_item['bundle_id'], outlet)
                )
            else:
                item = dict(raw_item)
                item['bundle_id'] = None
                expanded_items.append(item)

        # --- Existing per-product validation and totalling loop ---
        subtotal = Decimal('0.00')
        tax_total = Decimal('0.00')
        discount_total = Decimal('0.00')
        sale_items_to_create = []

        for item_data in expanded_items:
            from products.models import Product
            product = Product.objects.select_for_update().get(pk=item_data['product_id'])

            if not product.is_active:
                raise ValueError(
                    f"Product '{product.name}' (id={product.id}) is inactive."
                )

            quantity = item_data['quantity']
            unit_price = item_data['unit_price']

            if product.track_stock and product.stock_quantity < quantity:
                raise ValueError(
                    f"Insufficient stock for '{product.name}'. "
                    f"Available: {product.stock_quantity}, requested: {quantity}."
                )

            line_subtotal = unit_price * quantity
            item_discount_amount = Decimal('0.00')

            if item_data.get('discount_id'):
                from .models import Discount
                try:
                    discount = Discount.objects.get(
                        pk=item_data['discount_id'], is_active=True
                    )
                    item_discount_amount = apply_discount(line_subtotal, discount)
                except Discount.DoesNotExist:
                    pass

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
                'discount': Discount.objects.filter(
                    pk=item_data['discount_id']
                ).first() if item_data.get('discount_id') else None,
                'discount_amount': item_discount_amount,
                'line_total': line_total,
                'bundle_id': item_data.get('bundle_id'),
            })

        grand_total = subtotal + tax_total - discount_total

        # Payment validation (existing logic unchanged)
        total_paid = sum(p['amount'] for p in payments_data)
        if total_paid < grand_total:
            raise ValueError(
                f"Insufficient payment. Total: {grand_total}, paid: {total_paid}."
            )

        # Create Sale (existing logic unchanged)
        receipt_number = generate_receipt_number(outlet.id)
        shift = validated_data['shift']
        sale = Sale.objects.create(
            outlet=outlet,
            shift=shift,
            cashier_id=user.id,
            subtotal=subtotal,
            tax_total=tax_total,
            discount_total=discount_total,
            grand_total=grand_total,
            receipt_number=receipt_number,
        )

        # Create SaleItems — now includes bundle_id
        for item_data in sale_items_to_create:
            SaleItem.objects.create(
                sale=sale,
                product=item_data['product'],
                product_name=item_data['product_name'],
                unit_price=item_data['unit_price'],
                quantity=item_data['quantity'],
                tax_rate=item_data['tax_rate'],
                tax_amount=item_data['tax_amount'],
                discount=item_data['discount'],
                discount_amount=item_data['discount_amount'],
                line_total=item_data['line_total'],
                bundle_id=item_data['bundle_id'],   # <-- new
            )

        # Create Payments (existing logic unchanged)
        for p in payments_data:
            from .models import Payment
            Payment.objects.create(
                sale=sale,
                payment_method=p['payment_method'],
                amount=p['amount'],
                reference=p.get('reference', ''),
            )

        # FIFO stock deduction (Phase 11 enhancement)
        for item_data in sale_items_to_create:
            product = item_data['product']
            if product.track_stock:
                _deduct_stock(
                    product=product,
                    outlet=outlet,
                    quantity=item_data['quantity'],
                    sale=sale,
                    user_id=user.id,
                )

        try:
            submit_sale_for_fiscalization(sale)
        except Exception:
            pass

        return sale
```

---

## Phase 8: Tests

All tests use `TenantTestCase` + `TenantClient`. The shared base class creates fixtures once per class in `setUpTestData`.

```python
from decimal import Decimal

from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from rest_framework import status

from outlets.models import Outlet
from products.models import Category, Product, Bundle, BundleItem
from inventory.models import Supplier, ProductBatch, OutletStock, StockAuditLog
from sales.models import Discount, Sale, SaleItem, Shift, Payment
from users.models import User


class InventoryPhase11TestCase(TenantTestCase):
    """
    Shared fixtures for all Phase 11 test groups.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.outlet = Outlet.objects.create(name='Lira Central', outlet_type='supermarket')
        cls.outlet2 = Outlet.objects.create(name='Gulu Branch', outlet_type='supermarket')

        cls.category = Category.objects.create(
            name='Groceries', business_unit='supermarket', is_active=True
        )

        cls.product = Product.objects.create(
            name='Milk 1L', sku='MLK-001', category=cls.category,
            cost_price=Decimal('2000'), selling_price=Decimal('3000'),
            tax_rate=Decimal('0'), track_stock=True,
            stock_quantity=Decimal('100'), unit='piece', is_active=True,
        )
        cls.product2 = Product.objects.create(
            name='Bread Loaf', sku='BRD-001', category=cls.category,
            cost_price=Decimal('3000'), selling_price=Decimal('4500'),
            tax_rate=Decimal('0'), track_stock=True,
            stock_quantity=Decimal('50'), unit='piece', is_active=True,
        )
        cls.product_no_stock = Product.objects.create(
            name='Pepper', sku='PPR-001', category=cls.category,
            cost_price=Decimal('500'), selling_price=Decimal('1000'),
            tax_rate=Decimal('0'), track_stock=False,
            stock_quantity=Decimal('0'), unit='piece', is_active=True,
        )

        cls.supplier = Supplier.objects.create(name='Kampala Distributors')

        cls.outlet_stock = OutletStock.objects.create(
            outlet=cls.outlet, product=cls.product, quantity=Decimal('80')
        )
        cls.outlet_stock2 = OutletStock.objects.create(
            outlet=cls.outlet, product=cls.product2, quantity=Decimal('30')
        )

        cls.admin = User.objects.create_user(
            email='admin@test.com', password='pass123', role='admin'
        )
        cls.manager = User.objects.create_user(
            email='manager@test.com', password='pass123', role='manager'
        )
        cls.cashier = User.objects.create_user(
            email='cashier@test.com', password='pass123', role='cashier'
        )

    def setUp(self):
        self.client = TenantClient(self.tenant)

    def _auth(self, user):
        self.client.force_authenticate(user=user)


# ---------------------------------------------------------------------------
# Group 1: ProductBatch model + API (10 tests)
# ---------------------------------------------------------------------------

class ProductBatchAPITests(InventoryPhase11TestCase):

    def test_create_batch_as_admin(self):
        """Admin can create a batch with expiry_date."""
        self._auth(self.admin)
        resp = self.client.post('/api/inventory/batches/', {
            'product': self.product.id,
            'outlet': self.outlet.id,
            'supplier': self.supplier.id,
            'quantity': '20.000',
            'expiry_date': '2026-12-31',
            'cost_price': '2000',
        }, content_type='application/json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn('batch_number', resp.data)
        # batch_number auto-generated
        self.assertTrue(resp.data['batch_number'].startswith('BT-'))

    def test_batch_number_auto_generated_when_blank(self):
        """Omitting batch_number results in a BT- prefixed auto value."""
        self._auth(self.admin)
        resp = self.client.post('/api/inventory/batches/', {
            'product': self.product.id,
            'outlet': self.outlet.id,
            'quantity': '5.000',
        }, content_type='application/json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertRegex(resp.data['batch_number'], r'^BT-[A-F0-9]{8}$')

    def test_cashier_cannot_create_batch(self):
        """Cashier role is rejected on batch creation (write requires admin/manager)."""
        self._auth(self.cashier)
        resp = self.client.post('/api/inventory/batches/', {
            'product': self.product.id,
            'outlet': self.outlet.id,
            'quantity': '5.000',
        }, content_type='application/json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_batches_filterable_by_outlet(self):
        """Batches can be filtered to a specific outlet."""
        ProductBatch.objects.create(
            product=self.product, outlet=self.outlet, quantity=Decimal('10')
        )
        ProductBatch.objects.create(
            product=self.product, outlet=self.outlet2, quantity=Decimal('5')
        )
        self._auth(self.manager)
        resp = self.client.get(
            f'/api/inventory/batches/?outlet={self.outlet.id}'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        outlet_ids = {r['outlet'] for r in resp.data['results']}
        self.assertEqual(outlet_ids, {self.outlet.id})

    def test_zero_quantity_rejected(self):
        """Batch with quantity=0 is rejected by serializer validation."""
        self._auth(self.admin)
        resp = self.client.post('/api/inventory/batches/', {
            'product': self.product.id,
            'outlet': self.outlet.id,
            'quantity': '0.000',
        }, content_type='application/json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_batch_is_active_default_true(self):
        """New batches are active by default."""
        self._auth(self.admin)
        resp = self.client.post('/api/inventory/batches/', {
            'product': self.product.id,
            'outlet': self.outlet.id,
            'quantity': '3.000',
        }, content_type='application/json')
        self.assertTrue(resp.data['is_active'])

    def test_non_perishable_batch_null_expiry(self):
        """Batch without expiry_date is accepted (non-perishable)."""
        self._auth(self.admin)
        resp = self.client.post('/api/inventory/batches/', {
            'product': self.product.id,
            'outlet': self.outlet.id,
            'quantity': '10.000',
        }, content_type='application/json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(resp.data['expiry_date'])

    def test_expiry_before_filter(self):
        """?expiry_before= returns only batches expiring on or before the date."""
        ProductBatch.objects.create(
            product=self.product, outlet=self.outlet,
            quantity=Decimal('10'), expiry_date='2026-06-30',
        )
        ProductBatch.objects.create(
            product=self.product, outlet=self.outlet,
            quantity=Decimal('10'), expiry_date='2027-06-30',
        )
        self._auth(self.manager)
        resp = self.client.get('/api/inventory/batches/?expiry_before=2026-12-31')
        for r in resp.data['results']:
            if r['expiry_date']:
                self.assertLessEqual(r['expiry_date'], '2026-12-31')

    def test_unauthenticated_list_rejected(self):
        resp = self.client.get('/api/inventory/batches/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_not_allowed(self):
        """DELETE is not exposed on batches (http_method_names excludes delete)."""
        batch = ProductBatch.objects.create(
            product=self.product, outlet=self.outlet, quantity=Decimal('5')
        )
        self._auth(self.admin)
        resp = self.client.delete(f'/api/inventory/batches/{batch.id}/')
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


# ---------------------------------------------------------------------------
# Group 2: Expiring-soon endpoint (5 tests)
# ---------------------------------------------------------------------------

class ExpiringSoonTests(InventoryPhase11TestCase):

    def setUp(self):
        super().setUp()
        from django.utils import timezone
        from datetime import timedelta
        today = timezone.now().date()
        # Batch expiring in 10 days
        self.near_batch = ProductBatch.objects.create(
            product=self.product, outlet=self.outlet,
            quantity=Decimal('5'),
            expiry_date=today + timedelta(days=10),
        )
        # Batch expiring in 60 days
        self.far_batch = ProductBatch.objects.create(
            product=self.product, outlet=self.outlet,
            quantity=Decimal('5'),
            expiry_date=today + timedelta(days=60),
        )
        # Non-perishable batch (null expiry)
        self.nonperishable_batch = ProductBatch.objects.create(
            product=self.product2, outlet=self.outlet, quantity=Decimal('10')
        )

    def test_default_30_days_returns_near_not_far(self):
        self._auth(self.manager)
        resp = self.client.get('/api/inventory/expiring-soon/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [r['id'] for r in resp.data['results']]
        self.assertIn(self.near_batch.id, ids)
        self.assertNotIn(self.far_batch.id, ids)

    def test_null_expiry_batches_excluded(self):
        """Non-perishable batches (null expiry) never appear in results."""
        self._auth(self.manager)
        resp = self.client.get('/api/inventory/expiring-soon/?days=365')
        ids = [r['id'] for r in resp.data['results']]
        self.assertNotIn(self.nonperishable_batch.id, ids)

    def test_days_param_controls_window(self):
        """days=70 captures the 60-day batch; days=5 does not."""
        self._auth(self.manager)
        resp_wide = self.client.get('/api/inventory/expiring-soon/?days=70')
        resp_narrow = self.client.get('/api/inventory/expiring-soon/?days=5')
        ids_wide = [r['id'] for r in resp_wide.data['results']]
        ids_narrow = [r['id'] for r in resp_narrow.data['results']]
        self.assertIn(self.far_batch.id, ids_wide)
        self.assertNotIn(self.far_batch.id, ids_narrow)

    def test_invalid_days_param_returns_400(self):
        self._auth(self.manager)
        resp = self.client.get('/api/inventory/expiring-soon/?days=abc')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_outlet_id_filter(self):
        """outlet_id param restricts results to that outlet only."""
        other_batch = ProductBatch.objects.create(
            product=self.product, outlet=self.outlet2,
            quantity=Decimal('3'), expiry_date=self.near_batch.expiry_date,
        )
        self._auth(self.manager)
        resp = self.client.get(
            f'/api/inventory/expiring-soon/?outlet_id={self.outlet.id}'
        )
        ids = [r['id'] for r in resp.data['results']]
        self.assertNotIn(other_batch.id, ids)
        other_batch.delete()


# ---------------------------------------------------------------------------
# Group 3: FIFO batch deduction at checkout (8 tests)
# ---------------------------------------------------------------------------

class FIFODeductionTests(InventoryPhase11TestCase):

    def _open_shift(self, user):
        Shift.objects.filter(user_id=user.id, status='open').update(status='closed')
        return Shift.objects.create(
            outlet=self.outlet, user_id=user.id,
            status='open', opening_cash=Decimal('100000'),
        )

    def _checkout(self, items, shift):
        self._auth(self.cashier)
        payload = {
            'shift': shift.id,
            'items': items,
            'payments': [{'payment_method': 'cash', 'amount': '999999'}],
        }
        return self.client.post(
            '/api/checkout/', payload, content_type='application/json'
        )

    def setUp(self):
        super().setUp()
        from django.utils import timezone
        from datetime import timedelta
        today = timezone.now().date()
        # Two batches: earlier expiry first
        self.batch_early = ProductBatch.objects.create(
            product=self.product, outlet=self.outlet,
            quantity=Decimal('5'), expiry_date=today + timedelta(days=10),
        )
        self.batch_late = ProductBatch.objects.create(
            product=self.product, outlet=self.outlet,
            quantity=Decimal('10'), expiry_date=today + timedelta(days=30),
        )

    def test_fifo_deducts_earliest_batch_first(self):
        """Selling 3 units deducts from the earliest-expiry batch only."""
        shift = self._open_shift(self.cashier)
        self._checkout([{
            'product_id': self.product.id,
            'quantity': '3.000',
            'unit_price': '3000',
        }], shift)
        self.batch_early.refresh_from_db()
        self.batch_late.refresh_from_db()
        self.assertEqual(self.batch_early.quantity, Decimal('2'))
        self.assertEqual(self.batch_late.quantity, Decimal('10'))

    def test_fifo_spans_multiple_batches(self):
        """Selling 7 units exhausts batch_early (5) and takes 2 from batch_late."""
        shift = self._open_shift(self.cashier)
        self._checkout([{
            'product_id': self.product.id,
            'quantity': '7.000',
            'unit_price': '3000',
        }], shift)
        self.batch_early.refresh_from_db()
        self.batch_late.refresh_from_db()
        self.assertEqual(self.batch_early.quantity, Decimal('0'))
        self.assertFalse(self.batch_early.is_active)
        self.assertEqual(self.batch_late.quantity, Decimal('8'))

    def test_exhausted_batch_set_inactive(self):
        """A batch whose quantity reaches zero has is_active=False."""
        shift = self._open_shift(self.cashier)
        self._checkout([{
            'product_id': self.product.id,
            'quantity': '5.000',
            'unit_price': '3000',
        }], shift)
        self.batch_early.refresh_from_db()
        self.assertFalse(self.batch_early.is_active)

    def test_product_stock_quantity_decremented(self):
        """product.stock_quantity is decremented even when batches are used."""
        shift = self._open_shift(self.cashier)
        before = self.product.stock_quantity
        self._checkout([{
            'product_id': self.product.id,
            'quantity': '2.000',
            'unit_price': '3000',
        }], shift)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, before - Decimal('2'))

    def test_no_batches_uses_legacy_deduction(self):
        """Products without batches still deduct from stock_quantity directly."""
        shift = self._open_shift(self.cashier)
        before = self.product2.stock_quantity
        self._checkout([{
            'product_id': self.product2.id,
            'quantity': '1.000',
            'unit_price': '4500',
        }], shift)
        self.product2.refresh_from_db()
        self.assertEqual(self.product2.stock_quantity, before - Decimal('1'))

    def test_insufficient_batch_stock_rejects_checkout(self):
        """Requesting more than total batch stock raises an error."""
        shift = self._open_shift(self.cashier)
        resp = self._checkout([{
            'product_id': self.product.id,
            'quantity': '100.000',  # More than batch_early(5) + batch_late(10)
            'unit_price': '3000',
        }], shift)
        self.assertIn(resp.status_code, [
            status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY
        ])

    def test_stock_audit_log_created_for_batch_sale(self):
        """A StockAuditLog entry is created with movement_type='sale'."""
        shift = self._open_shift(self.cashier)
        before_count = StockAuditLog.objects.filter(
            product=self.product, movement_type='sale'
        ).count()
        self._checkout([{
            'product_id': self.product.id,
            'quantity': '1.000',
            'unit_price': '3000',
        }], shift)
        after_count = StockAuditLog.objects.filter(
            product=self.product, movement_type='sale'
        ).count()
        self.assertEqual(after_count, before_count + 1)

    def test_track_stock_false_skips_batch_deduction(self):
        """Products with track_stock=False do not trigger batch logic."""
        ProductBatch.objects.create(
            product=self.product_no_stock, outlet=self.outlet, quantity=Decimal('10')
        )
        shift = self._open_shift(self.cashier)
        resp = self._checkout([{
            'product_id': self.product_no_stock.id,
            'quantity': '999.000',
            'unit_price': '1000',
        }], shift)
        # Should succeed — track_stock=False means no stock check or batch deduction
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Group 4: Bundle model + API (7 tests)
# ---------------------------------------------------------------------------

class BundleAPITests(InventoryPhase11TestCase):

    def _bundle_payload(self, name='Breakfast Bundle', price='7500'):
        return {
            'name': name,
            'description': 'Milk + Bread combo',
            'selling_price': price,
            'is_active': True,
            'items': [
                {'product': self.product.id, 'quantity': '1.000'},
                {'product': self.product2.id, 'quantity': '1.000'},
            ],
        }

    def test_create_bundle_as_admin(self):
        """Admin can create a bundle with nested items."""
        self._auth(self.admin)
        resp = self.client.post(
            '/api/bundles/', self._bundle_payload(),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['name'], 'Breakfast Bundle')
        self.assertEqual(len(resp.data['items']), 2)

    def test_cashier_cannot_create_bundle(self):
        self._auth(self.cashier)
        resp = self.client.post(
            '/api/bundles/', self._bundle_payload(),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_bundle_with_no_items_rejected(self):
        self._auth(self.admin)
        payload = self._bundle_payload()
        payload['items'] = []
        resp = self.client.post('/api/bundles/', payload, content_type='application/json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_products_in_bundle_rejected(self):
        self._auth(self.admin)
        payload = self._bundle_payload()
        payload['items'] = [
            {'product': self.product.id, 'quantity': '1.000'},
            {'product': self.product.id, 'quantity': '2.000'},
        ]
        resp = self.client.post('/api/bundles/', payload, content_type='application/json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_stock_check_all_sufficient(self):
        """stock-check returns can_sell=True when all components have stock."""
        self._auth(self.manager)
        bundle = Bundle.objects.create(
            name='Test Bundle', selling_price=Decimal('7000'), is_active=True
        )
        BundleItem.objects.create(
            bundle=bundle, product=self.product, quantity=Decimal('1')
        )
        BundleItem.objects.create(
            bundle=bundle, product=self.product2, quantity=Decimal('1')
        )
        resp = self.client.get(
            f'/api/bundles/{bundle.id}/stock-check/?outlet_id={self.outlet.id}'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['can_sell'])

    def test_stock_check_insufficient_returns_false(self):
        """can_sell=False when a component has less stock than required."""
        self._auth(self.manager)
        bundle = Bundle.objects.create(
            name='Huge Bundle', selling_price=Decimal('10000'), is_active=True
        )
        BundleItem.objects.create(
            bundle=bundle, product=self.product, quantity=Decimal('9999')
        )
        resp = self.client.get(
            f'/api/bundles/{bundle.id}/stock-check/?outlet_id={self.outlet.id}'
        )
        self.assertFalse(resp.data['can_sell'])

    def test_stock_check_missing_outlet_id_returns_400(self):
        self._auth(self.manager)
        bundle = Bundle.objects.create(
            name='B1', selling_price=Decimal('5000'), is_active=True
        )
        resp = self.client.get(f'/api/bundles/{bundle.id}/stock-check/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Group 5: Bundle checkout integration (10 tests)
# ---------------------------------------------------------------------------

class BundleCheckoutTests(InventoryPhase11TestCase):

    def _open_shift(self, user):
        Shift.objects.filter(user_id=user.id, status='open').update(status='closed')
        return Shift.objects.create(
            outlet=self.outlet, user_id=user.id,
            status='open', opening_cash=Decimal('50000'),
        )

    def setUp(self):
        super().setUp()
        self.bundle = Bundle.objects.create(
            name='Breakfast Bundle',
            selling_price=Decimal('7000'),
            is_active=True,
        )
        BundleItem.objects.create(
            bundle=self.bundle, product=self.product, quantity=Decimal('1')
        )
        BundleItem.objects.create(
            bundle=self.bundle, product=self.product2, quantity=Decimal('1')
        )

    def _checkout(self, items, shift):
        self._auth(self.cashier)
        return self.client.post('/api/checkout/', {
            'shift': shift.id,
            'items': items,
            'payments': [{'payment_method': 'cash', 'amount': '999999'}],
        }, content_type='application/json')

    def test_bundle_checkout_creates_sale(self):
        """A checkout with bundle_id creates a Sale record."""
        shift = self._open_shift(self.cashier)
        before = Sale.objects.count()
        resp = self._checkout([{'bundle_id': self.bundle.id}], shift)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Sale.objects.count(), before + 1)

    def test_bundle_checkout_expands_to_multiple_sale_items(self):
        """One bundle line creates one SaleItem per component product."""
        shift = self._open_shift(self.cashier)
        resp = self._checkout([{'bundle_id': self.bundle.id}], shift)
        sale = Sale.objects.get(pk=resp.data['id'])
        self.assertEqual(sale.items.count(), 2)

    def test_sale_items_tagged_with_bundle_id(self):
        """All SaleItems from a bundle carry the correct bundle_id."""
        shift = self._open_shift(self.cashier)
        resp = self._checkout([{'bundle_id': self.bundle.id}], shift)
        sale = Sale.objects.get(pk=resp.data['id'])
        for item in sale.items.all():
            self.assertEqual(item.bundle_id, self.bundle.id)

    def test_regular_items_have_null_bundle_id(self):
        """SaleItems from non-bundle checkout have bundle_id=None."""
        shift = self._open_shift(self.cashier)
        resp = self._checkout([{
            'product_id': self.product.id,
            'quantity': '1.000',
            'unit_price': '3000',
        }], shift)
        sale = Sale.objects.get(pk=resp.data['id'])
        for item in sale.items.all():
            self.assertIsNone(item.bundle_id)

    def test_bundle_stock_deducted_per_component(self):
        """Stock is deducted for each component individually."""
        shift = self._open_shift(self.cashier)
        before_p1 = self.product.stock_quantity
        before_p2 = self.product2.stock_quantity
        self._checkout([{'bundle_id': self.bundle.id}], shift)
        self.product.refresh_from_db()
        self.product2.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, before_p1 - Decimal('1'))
        self.assertEqual(self.product2.stock_quantity, before_p2 - Decimal('1'))

    def test_inactive_bundle_rejected(self):
        """Checkout with an inactive bundle_id returns an error."""
        self.bundle.is_active = False
        self.bundle.save()
        shift = self._open_shift(self.cashier)
        resp = self._checkout([{'bundle_id': self.bundle.id}], shift)
        self.assertIn(resp.status_code, [
            status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY
        ])
        self.bundle.is_active = True
        self.bundle.save()

    def test_nonexistent_bundle_rejected(self):
        shift = self._open_shift(self.cashier)
        resp = self._checkout([{'bundle_id': 99999}], shift)
        self.assertIn(resp.status_code, [
            status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY
        ])

    def test_mixed_bundle_and_product_in_same_checkout(self):
        """A checkout can contain both a bundle line and a regular product line."""
        shift = self._open_shift(self.cashier)
        resp = self._checkout([
            {'bundle_id': self.bundle.id},
            {'product_id': self.product_no_stock.id, 'quantity': '1.000', 'unit_price': '1000'},
        ], shift)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        sale = Sale.objects.get(pk=resp.data['id'])
        # 2 bundle components + 1 direct product = 3 SaleItems
        self.assertEqual(sale.items.count(), 3)

    def test_product_id_and_bundle_id_both_set_rejected(self):
        """Providing both product_id and bundle_id on one line is rejected."""
        shift = self._open_shift(self.cashier)
        resp = self._checkout([{
            'product_id': self.product.id,
            'bundle_id': self.bundle.id,
            'quantity': '1.000',
            'unit_price': '3000',
        }], shift)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_neither_product_nor_bundle_rejected(self):
        """A checkout line with neither product_id nor bundle_id is rejected."""
        shift = self._open_shift(self.cashier)
        resp = self._checkout([{'quantity': '1.000', 'unit_price': '1000'}], shift)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
```

---

## Quality Checklist

Work through this list before opening a PR.

### Models

- [ ] `ProductBatch` has all 11 specified fields (batch_number, product, outlet, supplier, quantity, received_date, expiry_date, cost_price, is_active, created_at, updated_at)
- [ ] `ProductBatch.save()` auto-generates `batch_number` from `uuid4().hex[:8].upper()` when blank
- [ ] `ProductBatch.Meta.ordering = ['-created_at']`
- [ ] Composite index on `(product, outlet, is_active, expiry_date)` present
- [ ] `Bundle` has: name, description, selling_price (decimal_places=0), is_active, created_at, updated_at
- [ ] `BundleItem` has: bundle FK, product FK, quantity; `unique_together = ('bundle', 'product')`
- [ ] `SaleItem.bundle_id` is `IntegerField(null=True, blank=True, db_index=True)` — not a FK

### Serializers

- [ ] `ProductBatchSerializer` lists fields explicitly — no `fields = '__all__'`
- [ ] `ProductBatchCreateSerializer.validate_quantity` rejects <= 0
- [ ] `BundleCreateSerializer.validate_items` rejects empty list and duplicate products
- [ ] `BundleCreateSerializer.create()` wraps `Bundle` + `BundleItem` creation in `transaction.atomic()`
- [ ] `CheckoutItemSerializer` validates mutual exclusivity of `product_id` and `bundle_id`

### Views / Services

- [ ] `ProductBatchViewSet` excludes DELETE (`http_method_names` does not include `'delete'`)
- [ ] `ProductBatchViewSet.get_queryset()` applies `expiry_before` / `expiry_after` date filters
- [ ] `ExpiringSoonView` excludes null-expiry batches
- [ ] `ExpiringSoonView` rejects `days` outside 1–365 with 400
- [ ] `BundleViewSet.stock_check` returns `can_sell` flag and per-component `sufficient` bool
- [ ] `_deduct_fifo` uses `select_for_update()` and is called inside `transaction.atomic()`
- [ ] `_deduct_fifo` returns `False` (not raises) when no batches exist
- [ ] `_deduct_fifo` raises `ValueError` when batches exist but total is insufficient
- [ ] FIFO ordering: `expiry_date` ASC with `nulls_last=True`
- [ ] `_expand_bundle_items` raises `ValueError` for inactive bundle or inactive component
- [ ] Bundle price distribution uses proportional calculation; result quantized to `Decimal('1')`

### Migrations

- [ ] `makemigrations inventory` — creates `ProductBatch` table
- [ ] `makemigrations products` — creates `Bundle` and `BundleItem` tables
- [ ] `makemigrations sales` — adds `bundle_id` to `SaleItem`
- [ ] All three migrations run with `migrate_schemas` (not `migrate`)
- [ ] `migrate_schemas` completes without errors on a clean DB

### Tests

- [ ] 40+ test methods total across all 5 groups
- [ ] All test classes extend `TenantTestCase`
- [ ] All `self.client` instances are `TenantClient`
- [ ] Group 1: 10 ProductBatch API tests
- [ ] Group 2: 5 expiring-soon endpoint tests
- [ ] Group 3: 8 FIFO deduction tests
- [ ] Group 4: 7 Bundle API tests
- [ ] Group 5: 10 Bundle checkout integration tests
- [ ] All tests pass: `docker compose exec backend python manage.py test inventory products sales`

---

## API Reference

### Batch / Expiry Tracking

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/inventory/batches/` | Authenticated | List batches (filterable) |
| POST | `/api/inventory/batches/` | Admin / Manager | Create batch |
| GET | `/api/inventory/batches/{id}/` | Authenticated | Retrieve batch |
| PATCH | `/api/inventory/batches/{id}/` | Admin / Manager | Update batch |
| GET | `/api/inventory/expiring-soon/` | Authenticated | Batches expiring soon |

**Filters on `/api/inventory/batches/`**

| Param | Type | Example | Description |
|---|---|---|---|
| `product` | int | `?product=12` | Filter by product |
| `outlet` | int | `?outlet=1` | Filter by outlet |
| `is_active` | bool | `?is_active=true` | Active/inactive batches |
| `expiry_before` | date | `?expiry_before=2026-12-31` | Expires on or before date |
| `expiry_after` | date | `?expiry_after=2026-06-01` | Expires on or after date |

**Response `GET /api/inventory/batches/{id}/`:**
```json
{
  "id": 3,
  "batch_number": "BT-A1B2C3D4",
  "product": 12,
  "product_name": "Milk 1L",
  "outlet": 1,
  "outlet_name": "Lira Central",
  "supplier": 2,
  "supplier_name": "Kampala Distributors",
  "quantity": "18.000",
  "received_date": "2026-05-13",
  "expiry_date": "2026-05-28",
  "cost_price": "2000",
  "is_active": true,
  "created_at": "2026-05-13T08:00:00Z",
  "updated_at": "2026-05-13T08:00:00Z"
}
```

**Response `GET /api/inventory/expiring-soon/?days=30`:**
```json
{
  "days": 30,
  "threshold_date": "2026-06-12",
  "count": 2,
  "results": [
    {
      "id": 3,
      "batch_number": "BT-A1B2C3D4",
      "product": 12,
      "product_name": "Milk 1L",
      "expiry_date": "2026-05-28",
      ...
    }
  ]
}
```

---

### Bundles

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/bundles/` | Authenticated | List bundles |
| POST | `/api/bundles/` | Admin / Manager | Create bundle |
| GET | `/api/bundles/{id}/` | Authenticated | Retrieve bundle with items |
| PATCH | `/api/bundles/{id}/` | Admin / Manager | Update bundle |
| DELETE | `/api/bundles/{id}/` | Admin only | Delete bundle |
| GET | `/api/bundles/{id}/stock-check/?outlet_id=` | Authenticated | Per-component stock check |

**Response `GET /api/bundles/{id}/`:**
```json
{
  "id": 1,
  "name": "Breakfast Bundle",
  "description": "Milk + Bread combo",
  "selling_price": "7000",
  "is_active": true,
  "items": [
    {
      "id": 1,
      "product": 12,
      "product_name": "Milk 1L",
      "product_sku": "MLK-001",
      "quantity": "1.000"
    },
    {
      "id": 2,
      "product": 15,
      "product_name": "Bread Loaf",
      "product_sku": "BRD-001",
      "quantity": "1.000"
    }
  ],
  "created_at": "2026-05-13T10:00:00Z",
  "updated_at": "2026-05-13T10:00:00Z"
}
```

**Response `GET /api/bundles/{id}/stock-check/?outlet_id=1`:**
```json
{
  "bundle_id": 1,
  "bundle_name": "Breakfast Bundle",
  "outlet_id": 1,
  "can_sell": true,
  "components": [
    {
      "product_id": 12,
      "product_name": "Milk 1L",
      "required": "1.000",
      "available": "80.000",
      "sufficient": true
    },
    {
      "product_id": 15,
      "product_name": "Bread Loaf",
      "required": "1.000",
      "available": "30.000",
      "sufficient": true
    }
  ]
}
```

---

### Checkout (updated)

**POST `/api/checkout/`** now accepts `bundle_id` on any item line.

Request with a bundle line:
```json
{
  "shift": 5,
  "items": [
    { "bundle_id": 1 }
  ],
  "payments": [
    { "payment_method": "cash", "amount": "7000" }
  ]
}
```

Request mixing bundle and direct product:
```json
{
  "shift": 5,
  "items": [
    { "bundle_id": 1 },
    { "product_id": 20, "quantity": "2.000", "unit_price": "500" }
  ],
  "payments": [
    { "payment_method": "mobile_money", "amount": "8000", "reference": "MTN-XYZ" }
  ]
}
```

Response `201` (same as existing checkout response; `bundle_id` now visible on items):
```json
{
  "id": 312,
  "receipt_number": "S001-2026-0312",
  "grand_total": "7000",
  "items": [
    {
      "id": 801,
      "product": 12,
      "product_name": "Milk 1L",
      "quantity": "1.000",
      "unit_price": "3000",
      "bundle_id": 1,
      "line_total": "3000.00"
    },
    {
      "id": 802,
      "product": 15,
      "product_name": "Bread Loaf",
      "quantity": "1.000",
      "unit_price": "4000",
      "bundle_id": 1,
      "line_total": "4000.00"
    }
  ]
}
```

---

## curl Examples

### 1. Create a Product Batch

```bash
TOKEN="<admin access token>"

curl -s -X POST http://localhost:8000/api/inventory/batches/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "product": 12,
    "outlet": 1,
    "supplier": 2,
    "quantity": "50.000",
    "expiry_date": "2026-06-15",
    "cost_price": "1800"
  }' | jq .
```

Expected: `{"id": 5, "batch_number": "BT-...", "is_active": true, ...}`

---

### 2. List Expiring Batches (next 14 days)

```bash
curl -s "http://localhost:8000/api/inventory/expiring-soon/?days=14&outlet_id=1" \
  -H "Authorization: Bearer $TOKEN" | jq '{count: .count, threshold: .threshold_date}'
```

---

### 3. Create a Bundle

```bash
curl -s -X POST http://localhost:8000/api/bundles/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Breakfast Bundle",
    "description": "Milk 1L + Bread Loaf",
    "selling_price": "7000",
    "is_active": true,
    "items": [
      {"product": 12, "quantity": "1.000"},
      {"product": 15, "quantity": "1.000"}
    ]
  }' | jq '{id: .id, name: .name, items: (.items | length)}'
```

---

### 4. Check Bundle Stock at Outlet

```bash
curl -s "http://localhost:8000/api/bundles/1/stock-check/?outlet_id=1" \
  -H "Authorization: Bearer $TOKEN" | jq '{can_sell: .can_sell, components: .components}'
```

---

### 5. Checkout with a Bundle

```bash
# First open a shift
curl -s -X POST http://localhost:8000/api/shifts/open/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"outlet": 1, "opening_cash": "100000"}' | jq .id

SHIFT_ID=5

# Bundle checkout
curl -s -X POST http://localhost:8000/api/checkout/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"shift\": $SHIFT_ID,
    \"items\": [
      {\"bundle_id\": 1}
    ],
    \"payments\": [
      {\"payment_method\": \"cash\", \"amount\": \"7000\"}
    ]
  }" | jq '{receipt: .receipt_number, total: .grand_total, item_count: (.items | length)}'
```

Expected:
```json
{ "receipt": "S001-2026-0312", "total": "7000.00", "item_count": 2 }
```

---

### 6. Mixed Bundle + Direct Product Checkout

```bash
curl -s -X POST http://localhost:8000/api/checkout/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"shift\": $SHIFT_ID,
    \"items\": [
      {\"bundle_id\": 1},
      {\"product_id\": 20, \"quantity\": \"3.000\", \"unit_price\": \"500\"}
    ],
    \"payments\": [
      {\"payment_method\": \"cash\", \"amount\": \"8500\"}
    ]
  }" | jq '{item_count: (.items | length), total: .grand_total}'
```

---

### 7. FIFO Verification — Shell

```bash
# Create two batches for the same product with different expiry dates
curl -s -X POST http://localhost:8000/api/inventory/batches/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"product": 12, "outlet": 1, "quantity": "5.000", "expiry_date": "2026-05-20"}' | jq .id

curl -s -X POST http://localhost:8000/api/inventory/batches/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"product": 12, "outlet": 1, "quantity": "10.000", "expiry_date": "2026-06-30"}' | jq .id

# Sell 7 units — expect first batch (5) exhausted, second batch at 8
curl -s -X POST http://localhost:8000/api/checkout/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"shift\": $SHIFT_ID, \"items\": [{\"product_id\": 12, \"quantity\": \"7.000\", \"unit_price\": \"3000\"}], \"payments\": [{\"payment_method\": \"cash\", \"amount\": \"21000\"}]}" | jq .

# Verify batch quantities
curl -s "http://localhost:8000/api/inventory/batches/?product=12&outlet=1" \
  -H "Authorization: Bearer $TOKEN" | jq '.results[] | {batch_number, quantity, is_active}'
```

---

## Implementation Order

Execute phases in sequence. Each phase has a concrete deliverable before moving to the next.

| # | Phase | Files changed | Deliverable | Verify with |
|---|---|---|---|---|
| 1 | `ProductBatch` model | `inventory/models.py` | Migration in `inventory/migrations/` | `showmigrations inventory` |
| 2 | Batch serializer + ViewSet + URLs | `inventory/serializers.py`, `inventory/views.py`, `inventory/urls.py` | `GET /api/inventory/batches/` returns 200 | `curl GET /api/inventory/batches/` |
| 3 | FIFO deduction in checkout service | `sales/services.py` | Batch quantities decrement on checkout | Shell: sell product with 2 batches, inspect batch quantities |
| 4 | Expiring-soon endpoint | `inventory/views.py`, `inventory/urls.py` | `GET /api/inventory/expiring-soon/` returns list | `curl GET /api/inventory/expiring-soon/?days=30` |
| 5 | `Bundle` + `BundleItem` models | `products/models.py` | Migrations in `products/migrations/` | `showmigrations products` |
| 6 | Bundle serializer + ViewSet + URLs | `products/serializers.py`, `products/views.py`, `products/urls.py` | `GET /api/bundles/` returns 200; `stock-check` action works | `curl GET /api/bundles/` |
| 7a | `SaleItem.bundle_id` field | `sales/models.py` | Migration in `sales/migrations/` | `showmigrations sales` |
| 7b | `CheckoutItemSerializer` — bundle path | `sales/serializers.py` | Sending `bundle_id` passes validation | Python shell import check |
| 7c | Bundle expansion in `process_checkout` | `sales/services.py` | Bundle checkout creates one SaleItem per component | `curl POST /api/checkout/` with `bundle_id` |
| 8 | Tests — all 5 groups | `inventory/tests.py`, `products/tests.py`, `sales/tests.py` | 40+ tests pass | `manage.py test inventory products sales` |

---

*Last updated: 2026-05-13*  
*Author: Kakebe Technologies backend team*  
*Branch: `feat-phase-11-inventory-enhancements`*
