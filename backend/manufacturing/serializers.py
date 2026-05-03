from rest_framework import serializers
from .models import BillOfMaterials, BOMItem, ProductionOrder, ProductionOrderItem, WorkInProgress
from products.models import Product
from outlets.models import Outlet
from decimal import Decimal


class BOMItemSerializer(serializers.ModelSerializer):
    raw_material_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='raw_material'
    )
    raw_material_name = serializers.ReadOnlyField(source='raw_material.name')

    class Meta:
        model = BOMItem
        fields = [
            'id', 'raw_material_id', 'raw_material_name', 
            'quantity_required', 'unit', 'waste_factor_pct', 
            'effective_quantity'
        ]
        read_only_fields = ['effective_quantity']


class BillOfMaterialsSerializer(serializers.ModelSerializer):
    finished_product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='finished_product'
    )
    finished_product_name = serializers.ReadOnlyField(source='finished_product.name')
    finished_product_sku = serializers.ReadOnlyField(source='finished_product.sku')
    items = BOMItemSerializer(many=True)
    items_count = serializers.SerializerMethodField()

    class Meta:
        model = BillOfMaterials
        fields = [
            'id', 'name', 'version', 'finished_product_id', 
            'finished_product_name', 'finished_product_sku',
            'output_quantity', 'output_unit', 'unit_cost', 
            'is_active', 'notes', 'items', 'items_count',
            'created_by_id', 'created_at', 'updated_at'
        ]
        read_only_fields = ['unit_cost', 'created_by_id', 'created_at', 'updated_at']

    def get_items_count(self, obj):
        return obj.items.count()

    def validate(self, data):
        items = data.get('items', [])
        finished_product = data.get('finished_product')
        seen = set()
        for item in items:
            rm = item['raw_material']
            if finished_product and rm.id == finished_product.id:
                raise serializers.ValidationError("A BOM item cannot use the finished product as a raw material.")
            if rm.id in seen:
                raise serializers.ValidationError(f"Duplicate raw material: {rm.name}")
            seen.add(rm.id)
        return data

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        bom = BillOfMaterials.objects.create(**validated_data)
        for item_data in items_data:
            BOMItem.objects.create(bom=bom, **item_data)
        
        # Initial cost calculation
        bom.unit_cost = bom.compute_unit_cost()
        bom.save()
        return bom

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        
        # Update BOM fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update items if provided (pattern: delete and recreate)
        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                BOMItem.objects.create(bom=instance, **item_data)
        
        # Recompute cost
        instance.unit_cost = instance.compute_unit_cost()
        instance.save()
        return instance


class ProductionOrderItemSerializer(serializers.ModelSerializer):
    raw_material_name = serializers.ReadOnlyField(source='raw_material.name')

    class Meta:
        model = ProductionOrderItem
        fields = [
            'id', 'raw_material', 'raw_material_name', 
            'quantity_planned', 'quantity_actual', 'unit', 
            'unit_cost', 'line_cost'
        ]


class WorkInProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkInProgress
        fields = [
            'id', 'production_order', 'snapshot_date', 
            'materials_consumed_value', 'percentage_complete', 
            'notes', 'recorded_by_id', 'created_at'
        ]
        read_only_fields = ['recorded_by_id', 'created_at']


class ProductionOrderSerializer(serializers.ModelSerializer):
    bom_id = serializers.PrimaryKeyRelatedField(
        queryset=BillOfMaterials.objects.all(), source='bom'
    )
    bom_name = serializers.ReadOnlyField(source='bom.name')
    outlet_id = serializers.PrimaryKeyRelatedField(
        queryset=Outlet.objects.all(), source='outlet'
    )
    outlet_name = serializers.ReadOnlyField(source='outlet.name')
    required_materials = serializers.SerializerMethodField()
    consumed_materials = ProductionOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = ProductionOrder
        fields = [
            'id', 'order_number', 'bom_id', 'bom_name', 
            'quantity_to_produce', 'quantity_produced', 'status',
            'planned_start', 'actual_start', 'completed_at',
            'outlet_id', 'outlet_name', 'ordered_by_id',
            'total_material_cost', 'notes', 'required_materials',
            'consumed_materials', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'order_number', 'quantity_produced', 'status', 
            'actual_start', 'completed_at', 'ordered_by_id', 
            'total_material_cost', 'created_at', 'updated_at'
        ]

    def validate_bom_id(self, value):
        if not value.is_active:
            raise serializers.ValidationError("Cannot create production order from an inactive BOM.")
        return value

    def get_required_materials(self, obj):
        from inventory.models import OutletStock
        materials = obj.get_required_materials()
        result = []
        for m in materials:
            stock = OutletStock.objects.filter(
                outlet=obj.outlet, product=m['raw_material']
            ).first()
            available = stock.quantity if stock else Decimal('0')
            result.append({
                'raw_material': m['raw_material'].name,
                'quantity_needed': str(m['quantity_needed']),
                'unit': m['unit'],
                'available': str(available),
                'sufficient': available >= m['quantity_needed']
            })
        return result


class BOMCostBreakdownSerializer(serializers.Serializer):
    bom = serializers.CharField(source='name')
    finished_product = serializers.CharField(source='finished_product.name')
    output_quantity = serializers.SerializerMethodField()
    total_batch_cost = serializers.SerializerMethodField()
    unit_cost = serializers.DecimalField(max_digits=15, decimal_places=2)
    items = serializers.SerializerMethodField()

    def get_output_quantity(self, obj):
        return f"{obj.output_quantity} {obj.output_unit}"

    def get_total_batch_cost(self, obj):
        total = Decimal('0')
        for item in obj.items.select_related('raw_material').all():
            total += item.effective_quantity * (item.raw_material.cost_price or Decimal('0'))
        return total.quantize(Decimal('0.01'))

    def get_items(self, obj):
        return [
            {
                'raw_material': item.raw_material.name,
                'quantity_required': f"{item.quantity_required} {item.unit}",
                'waste_factor_pct': str(item.waste_factor_pct),
                'effective_quantity': f"{item.effective_quantity} {item.unit}",
                'unit_cost': str(item.raw_material.cost_price or 0),
                'line_cost': str((item.effective_quantity * (item.raw_material.cost_price or 0)).quantize(Decimal('0.01')))
            }
            for item in obj.items.select_related('raw_material').all()
        ]
