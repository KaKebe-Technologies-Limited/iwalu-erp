from django.contrib import admin
from .models import BillOfMaterials, BOMItem, ProductionOrder, ProductionOrderItem, WorkInProgress


class BOMItemInline(admin.TabularInline):
    model = BOMItem
    extra = 1


@admin.register(BillOfMaterials)
class BillOfMaterialsAdmin(admin.ModelAdmin):
    list_display = ('name', 'finished_product', 'version', 'output_quantity', 'output_unit', 'unit_cost', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'finished_product__name')
    inlines = [BOMItemInline]


class ProductionOrderItemInline(admin.TabularInline):
    model = ProductionOrderItem
    extra = 0
    readonly_fields = ('raw_material', 'quantity_planned', 'quantity_actual', 'unit', 'unit_cost', 'line_cost')


@admin.register(ProductionOrder)
class ProductionOrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'bom', 'quantity_to_produce', 'status', 'outlet', 'created_at')
    list_filter = ('status', 'outlet')
    search_fields = ('order_number', 'bom__name')
    inlines = [ProductionOrderItemInline]
    readonly_fields = ('order_number', 'ordered_by_id', 'total_material_cost', 'completed_at', 'actual_start')


@admin.register(WorkInProgress)
class WorkInProgressAdmin(admin.ModelAdmin):
    list_display = ('production_order', 'snapshot_date', 'percentage_complete', 'recorded_by_id')
    list_filter = ('snapshot_date',)
