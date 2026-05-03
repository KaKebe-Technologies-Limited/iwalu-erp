from django.contrib import admin
from .models import MenuCategory, MenuItem, MenuItemIngredient, MenuOrder, MenuOrderItem, WasteLog

@admin.register(MenuCategory)
class MenuCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_order', 'is_active')
    list_editable = ('display_order', 'is_active')

@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'is_available')
    list_filter = ('category', 'is_available', 'has_bom')
    search_fields = ('name', 'description')

@admin.register(MenuItemIngredient)
class MenuItemIngredientAdmin(admin.ModelAdmin):
    list_display = ('menu_item', 'product', 'quantity_per_serving', 'unit')
    list_filter = ('menu_item', 'product')

class MenuOrderItemInline(admin.TabularInline):
    model = MenuOrderItem
    extra = 0

@admin.register(MenuOrder)
class MenuOrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'order_type', 'status', 'total_amount', 'created_at')
    list_filter = ('status', 'order_type', 'created_at')
    search_fields = ('order_number', 'table_number')
    inlines = [MenuOrderItemInline]

@admin.register(WasteLog)
class WasteLogAdmin(admin.ModelAdmin):
    list_display = ('product', 'quantity', 'unit', 'reason', 'cost_value', 'recorded_at')
    list_filter = ('reason', 'recorded_at')
    search_fields = ('product__name', 'notes')
