from django.contrib import admin
from .models import (
    Supplier, OutletStock, PurchaseOrder, PurchaseOrderItem,
    StockTransfer, StockTransferItem, StockAuditLog,
)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'email', 'phone', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'contact_person', 'email')


@admin.register(OutletStock)
class OutletStockAdmin(admin.ModelAdmin):
    list_display = ('outlet', 'product', 'quantity', 'updated_at')
    list_filter = ('outlet',)
    search_fields = ('product__name',)


class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 1


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('po_number', 'supplier', 'outlet', 'status', 'total_cost', 'created_at')
    list_filter = ('status', 'outlet')
    search_fields = ('po_number', 'supplier__name')
    inlines = [PurchaseOrderItemInline]


class StockTransferItemInline(admin.TabularInline):
    model = StockTransferItem
    extra = 1


@admin.register(StockTransfer)
class StockTransferAdmin(admin.ModelAdmin):
    list_display = ('transfer_number', 'from_outlet', 'to_outlet', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('transfer_number',)
    inlines = [StockTransferItemInline]


@admin.register(StockAuditLog)
class StockAuditLogAdmin(admin.ModelAdmin):
    list_display = ('product', 'outlet', 'movement_type', 'quantity_change',
                    'quantity_before', 'quantity_after', 'created_at')
    list_filter = ('movement_type', 'outlet')
    search_fields = ('product__name',)
    readonly_fields = ('product', 'outlet', 'movement_type', 'quantity_change',
                       'quantity_before', 'quantity_after', 'reference_type',
                       'reference_id', 'user_id', 'notes', 'created_at')

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
