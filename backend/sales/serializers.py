from rest_framework import serializers
from .models import Discount, Shift, Sale, SaleItem, Payment


class DiscountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Discount
        fields = ['id', 'name', 'discount_type', 'value', 'is_active',
                  'valid_from', 'valid_until', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shift
        fields = ['id', 'outlet', 'user_id', 'status', 'opening_cash',
                  'closing_cash', 'expected_cash', 'notes', 'opened_at',
                  'closed_at']
        read_only_fields = ['id', 'user_id', 'status', 'closing_cash',
                            'expected_cash', 'opened_at', 'closed_at']


class OpenShiftSerializer(serializers.Serializer):
    outlet = serializers.IntegerField()
    opening_cash = serializers.DecimalField(max_digits=12, decimal_places=2)


class CloseShiftSerializer(serializers.Serializer):
    closing_cash = serializers.DecimalField(max_digits=12, decimal_places=2)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'payment_method', 'amount', 'reference', 'created_at']
        read_only_fields = ['id', 'created_at']


class SaleItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleItem
        fields = ['id', 'product', 'product_name', 'unit_price', 'quantity',
                  'tax_rate', 'tax_amount', 'discount', 'discount_amount',
                  'line_total']
        read_only_fields = ['id']


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Sale
        fields = ['id', 'receipt_number', 'outlet', 'shift', 'cashier_id',
                  'subtotal', 'tax_total', 'discount_total', 'grand_total',
                  'discount', 'status', 'notes', 'items', 'payments',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'receipt_number', 'created_at', 'updated_at']


class SaleListSerializer(serializers.ModelSerializer):
    """Lighter serializer for list views (no nested items/payments)."""
    class Meta:
        model = Sale
        fields = ['id', 'receipt_number', 'outlet', 'shift', 'cashier_id',
                  'grand_total', 'status', 'created_at']
        read_only_fields = ['id', 'receipt_number', 'created_at']


# Checkout input serializers

class CheckoutItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3)
    discount_id = serializers.IntegerField(required=False, allow_null=True)


class CheckoutPaymentSerializer(serializers.Serializer):
    payment_method = serializers.ChoiceField(
        choices=['cash', 'bank', 'mobile_money', 'card'],
    )
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    reference = serializers.CharField(required=False, allow_blank=True, default='')


class CheckoutSerializer(serializers.Serializer):
    items = CheckoutItemSerializer(many=True, min_length=1)
    payments = CheckoutPaymentSerializer(many=True, min_length=1)
    discount_id = serializers.IntegerField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default='')
