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
    outlet_stock is injected from context['outlet_stock_map'] to avoid N+1.
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
    quantity = serializers.DecimalField(max_digits=10, decimal_places=3, min_value=Decimal('0.001'))
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    discount_id = serializers.IntegerField(required=False, allow_null=True)


class MobileTransactionSerializer(serializers.Serializer):
    client_uuid = serializers.UUIDField()
    created_at = serializers.DateTimeField()
    items = MobileSaleItemInputSerializer(many=True)
    payments = MobilePaymentInputSerializer(many=True)
    notes = serializers.CharField(
        required=False, allow_blank=True, default='', max_length=500
    )


class MobileBatchSyncSerializer(serializers.Serializer):
    device_id = serializers.RegexField(r'^[a-zA-Z0-9_\-]{8,64}$', max_length=64)
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
