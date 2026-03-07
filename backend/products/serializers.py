from rest_framework import serializers
from .models import Category, Product


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'business_unit', 'description', 'parent',
                  'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'name', 'sku', 'barcode', 'category', 'category_name',
                  'cost_price', 'selling_price', 'tax_rate', 'track_stock',
                  'stock_quantity', 'reorder_level', 'unit', 'is_active',
                  'is_low_stock', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class StockAdjustmentSerializer(serializers.Serializer):
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3)
    reason = serializers.CharField(max_length=255)
