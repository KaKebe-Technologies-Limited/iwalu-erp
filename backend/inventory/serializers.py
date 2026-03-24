from decimal import Decimal
from rest_framework import serializers
from .models import (
    Supplier, OutletStock, PurchaseOrder, PurchaseOrderItem,
    StockTransfer, StockTransferItem, StockAuditLog,
)


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class OutletStockSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    outlet_name = serializers.CharField(source='outlet.name', read_only=True)

    class Meta:
        model = OutletStock
        fields = '__all__'
        read_only_fields = ('updated_at',)


# --- Purchase Orders ---

class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = PurchaseOrderItem
        fields = ('id', 'product', 'product_name', 'quantity_ordered',
                  'quantity_received', 'unit_cost', 'line_total')
        read_only_fields = ('quantity_received', 'line_total')


class PurchaseOrderItemCreateSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity_ordered = serializers.DecimalField(max_digits=12, decimal_places=3)
    unit_cost = serializers.DecimalField(max_digits=12, decimal_places=2)

    def validate_quantity_ordered(self, value):
        if value <= 0:
            raise serializers.ValidationError('Quantity must be positive.')
        return value

    def validate_unit_cost(self, value):
        if value <= 0:
            raise serializers.ValidationError('Unit cost must be positive.')
        return value


class PurchaseOrderSerializer(serializers.ModelSerializer):
    items = PurchaseOrderItemSerializer(many=True, read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    outlet_name = serializers.CharField(source='outlet.name', read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = '__all__'
        read_only_fields = ('po_number', 'ordered_by', 'status', 'total_cost',
                            'created_at', 'updated_at')


class PurchaseOrderCreateSerializer(serializers.Serializer):
    supplier_id = serializers.IntegerField()
    outlet_id = serializers.IntegerField()
    expected_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, default='')
    items = PurchaseOrderItemCreateSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError('At least one item is required.')
        return value


class ReceiveItemSerializer(serializers.Serializer):
    po_item_id = serializers.IntegerField()
    quantity_received = serializers.DecimalField(max_digits=12, decimal_places=3)

    def validate_quantity_received(self, value):
        if value <= 0:
            raise serializers.ValidationError('Quantity must be positive.')
        return value


class ReceivePurchaseOrderSerializer(serializers.Serializer):
    items = ReceiveItemSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError('At least one item is required.')
        return value


# --- Stock Transfers ---

class StockTransferItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = StockTransferItem
        fields = ('id', 'product', 'product_name', 'quantity', 'quantity_received')
        read_only_fields = ('quantity_received',)


class StockTransferItemCreateSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3)

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError('Quantity must be positive.')
        return value


class StockTransferSerializer(serializers.ModelSerializer):
    items = StockTransferItemSerializer(many=True, read_only=True)
    from_outlet_name = serializers.CharField(source='from_outlet.name', read_only=True)
    to_outlet_name = serializers.CharField(source='to_outlet.name', read_only=True)

    class Meta:
        model = StockTransfer
        fields = '__all__'
        read_only_fields = ('transfer_number', 'initiated_by', 'status',
                            'created_at', 'updated_at')


class StockTransferCreateSerializer(serializers.Serializer):
    from_outlet_id = serializers.IntegerField()
    to_outlet_id = serializers.IntegerField()
    notes = serializers.CharField(required=False, default='')
    items = StockTransferItemCreateSerializer(many=True)

    def validate(self, data):
        if data['from_outlet_id'] == data['to_outlet_id']:
            raise serializers.ValidationError(
                {'to_outlet_id': 'Cannot transfer to the same outlet.'}
            )
        if not data['items']:
            raise serializers.ValidationError(
                {'items': 'At least one item is required.'}
            )
        return data


class ReceiveTransferItemSerializer(serializers.Serializer):
    transfer_item_id = serializers.IntegerField()
    quantity_received = serializers.DecimalField(max_digits=12, decimal_places=3)

    def validate_quantity_received(self, value):
        if value <= 0:
            raise serializers.ValidationError('Quantity must be positive.')
        return value


class ReceiveTransferSerializer(serializers.Serializer):
    items = ReceiveTransferItemSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError('At least one item is required.')
        return value


# --- Audit Log ---

class StockAuditLogSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    outlet_name = serializers.CharField(source='outlet.name', read_only=True, default=None)
    movement_type_display = serializers.CharField(
        source='get_movement_type_display', read_only=True,
    )

    class Meta:
        model = StockAuditLog
        fields = '__all__'
