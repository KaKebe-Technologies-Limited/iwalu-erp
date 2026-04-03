from rest_framework import serializers
from .models import (
    Pump, Tank, TankReading, PumpReading,
    FuelDelivery, FuelReconciliation,
)


# ---------- Pump ----------

class PumpSerializer(serializers.ModelSerializer):
    outlet_name = serializers.CharField(source='outlet.name', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Pump
        fields = [
            'id', 'outlet', 'outlet_name', 'product', 'product_name',
            'pump_number', 'name', 'status', 'status_display',
            'created_at', 'updated_at',
        ]
        read_only_fields = ('created_at', 'updated_at')


# ---------- Tank ----------

class TankSerializer(serializers.ModelSerializer):
    outlet_name = serializers.CharField(source='outlet.name', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    fill_percentage = serializers.FloatField(read_only=True)
    is_low = serializers.BooleanField(read_only=True)

    class Meta:
        model = Tank
        fields = [
            'id', 'outlet', 'outlet_name', 'product', 'product_name',
            'name', 'capacity', 'current_level', 'reorder_level',
            'is_active', 'fill_percentage', 'is_low',
            'created_at', 'updated_at',
        ]
        read_only_fields = ('current_level', 'created_at', 'updated_at')


# ---------- Tank Reading ----------

class TankReadingSerializer(serializers.ModelSerializer):
    tank_name = serializers.CharField(source='tank.name', read_only=True)
    reading_type_display = serializers.CharField(
        source='get_reading_type_display', read_only=True,
    )

    class Meta:
        model = TankReading
        fields = [
            'id', 'tank', 'tank_name', 'reading_level', 'reading_type',
            'reading_type_display', 'recorded_by', 'notes', 'reading_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = ('recorded_by', 'created_at', 'updated_at')


class RecordTankReadingSerializer(serializers.Serializer):
    reading_level = serializers.DecimalField(max_digits=12, decimal_places=3)
    reading_type = serializers.ChoiceField(choices=['manual', 'automatic'])
    reading_at = serializers.DateTimeField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True, default='', max_length=2000)

    def validate_reading_level(self, value):
        if value < 0:
            raise serializers.ValidationError('Reading level cannot be negative.')
        return value


# ---------- Pump Reading ----------

class PumpReadingSerializer(serializers.ModelSerializer):
    pump_number = serializers.IntegerField(source='pump.pump_number', read_only=True)
    pump_name = serializers.CharField(source='pump.name', read_only=True)
    volume_dispensed = serializers.DecimalField(
        read_only=True, max_digits=12, decimal_places=3,
    )

    class Meta:
        model = PumpReading
        fields = [
            'id', 'pump', 'pump_number', 'pump_name', 'shift',
            'opening_reading', 'closing_reading', 'volume_dispensed',
            'recorded_by', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ('recorded_by', 'created_at', 'updated_at')


class OpenPumpReadingSerializer(serializers.Serializer):
    pump_id = serializers.IntegerField()
    shift_id = serializers.IntegerField()
    opening_reading = serializers.DecimalField(max_digits=12, decimal_places=3)

    def validate_opening_reading(self, value):
        if value < 0:
            raise serializers.ValidationError('Opening reading cannot be negative.')
        return value


class ClosePumpReadingSerializer(serializers.Serializer):
    closing_reading = serializers.DecimalField(max_digits=12, decimal_places=3)
    notes = serializers.CharField(required=False, allow_blank=True, default='', max_length=2000)

    def validate_closing_reading(self, value):
        if value < 0:
            raise serializers.ValidationError('Closing reading cannot be negative.')
        return value


# ---------- Fuel Delivery ----------

class FuelDeliverySerializer(serializers.ModelSerializer):
    tank_name = serializers.CharField(source='tank.name', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)

    class Meta:
        model = FuelDelivery
        fields = [
            'id', 'tank', 'tank_name', 'supplier', 'supplier_name',
            'delivery_date', 'volume_ordered', 'volume_received',
            'unit_cost', 'total_cost', 'delivery_note_number',
            'tank_level_before', 'tank_level_after', 'received_by',
            'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = (
            'tank_level_before', 'tank_level_after', 'total_cost',
            'received_by', 'created_at', 'updated_at',
        )


class FuelDeliveryCreateSerializer(serializers.Serializer):
    tank_id = serializers.IntegerField()
    supplier_id = serializers.IntegerField()
    delivery_date = serializers.DateTimeField()
    volume_ordered = serializers.DecimalField(
        max_digits=12, decimal_places=3, required=False, allow_null=True,
    )
    volume_received = serializers.DecimalField(max_digits=12, decimal_places=3)
    unit_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
    delivery_note_number = serializers.CharField(
        required=False, allow_blank=True, default='',
    )
    notes = serializers.CharField(required=False, allow_blank=True, default='', max_length=2000)

    def validate_volume_received(self, value):
        if value <= 0:
            raise serializers.ValidationError('Volume must be positive.')
        return value

    def validate_unit_cost(self, value):
        if value <= 0:
            raise serializers.ValidationError('Unit cost must be positive.')
        return value


# ---------- Fuel Reconciliation ----------

class FuelReconciliationSerializer(serializers.ModelSerializer):
    tank_name = serializers.CharField(source='tank.name', read_only=True)
    outlet_name = serializers.CharField(source='outlet.name', read_only=True)
    variance_type_display = serializers.CharField(
        source='get_variance_type_display', read_only=True,
    )

    class Meta:
        model = FuelReconciliation
        fields = [
            'id', 'date', 'outlet', 'outlet_name', 'tank', 'tank_name',
            'opening_stock', 'closing_stock', 'total_received',
            'total_dispensed', 'expected_closing', 'variance',
            'variance_percentage', 'variance_type', 'variance_type_display',
            'status', 'notes', 'reconciled_by', 'created_at', 'updated_at',
        ]
        read_only_fields = (
            'opening_stock', 'closing_stock', 'total_received',
            'total_dispensed', 'expected_closing', 'variance',
            'variance_percentage', 'variance_type', 'reconciled_by',
            'created_at', 'updated_at',
        )


class ReconciliationRequestSerializer(serializers.Serializer):
    tank_id = serializers.IntegerField()
    date = serializers.DateField()
    closing_stock = serializers.DecimalField(
        max_digits=12, decimal_places=3, required=False, allow_null=True,
    )
    notes = serializers.CharField(required=False, allow_blank=True, default='', max_length=2000)
