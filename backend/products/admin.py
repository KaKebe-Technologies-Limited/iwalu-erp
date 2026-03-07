from django.contrib import admin
from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'business_unit', 'parent', 'is_active']
    list_filter = ['business_unit', 'is_active']
    search_fields = ['name']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'sku', 'category', 'selling_price', 'stock_quantity',
                    'is_active']
    list_filter = ['category__business_unit', 'is_active', 'track_stock']
    search_fields = ['name', 'sku', 'barcode']
