from rest_framework import serializers
from .models import MenuCategory, MenuItem, MenuItemIngredient, MenuOrder, MenuOrderItem, WasteLog
from products.models import Product


class MenuCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuCategory
        fields = ['id', 'name', 'description', 'display_order', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class MenuItemIngredientSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product'
    )

    class Meta:
        model = MenuItemIngredient
        fields = ['id', 'product_id', 'product_name', 'quantity_per_serving', 'unit', 'created_at']
        read_only_fields = ['id', 'created_at']


class MenuItemSerializer(serializers.ModelSerializer):
    category_detail = MenuCategorySerializer(source='category', read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=MenuCategory.objects.all(), source='category'
    )
    ingredients = MenuItemIngredientSerializer(many=True, read_only=True)

    class Meta:
        model = MenuItem
        fields = [
            'id', 'name', 'category_id', 'category_detail', 'description',
            'price', 'cost_price', 'has_bom', 'is_available',
            'preparation_time_minutes', 'ingredients', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'cost_price', 'created_at', 'updated_at']


class MenuOrderItemSerializer(serializers.ModelSerializer):
    menu_item_name = serializers.CharField(source='menu_item.name', read_only=True)

    class Meta:
        model = MenuOrderItem
        fields = [
            'id', 'menu_item', 'menu_item_name', 'quantity', 'unit_price',
            'line_total', 'special_instructions'
        ]
        read_only_fields = ['id', 'line_total']


class MenuOrderSerializer(serializers.ModelSerializer):
    items = MenuOrderItemSerializer(many=True, read_only=True)
    outlet_name = serializers.CharField(source='outlet.name', read_only=True)

    class Meta:
        model = MenuOrder
        fields = [
            'id', 'order_number', 'order_type', 'table_number', 'status',
            'outlet', 'outlet_name', 'cashier_id', 'total_amount', 'notes',
            'items', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'order_number', 'outlet', 'cashier_id', 'total_amount', 'created_at', 'updated_at']


class WasteLogSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product'
    )

    class Meta:
        model = WasteLog
        fields = [
            'id', 'product_id', 'product_name', 'quantity', 'unit',
            'reason', 'cost_value', 'recorded_by_id', 'recorded_at', 'notes', 'created_at'
        ]
        read_only_fields = ['id', 'cost_value', 'recorded_by_id', 'created_at']
