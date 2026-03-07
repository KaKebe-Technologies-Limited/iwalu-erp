from django.contrib import admin
from .models import Discount, Shift, Sale, SaleItem, Payment


@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):
    list_display = ['name', 'discount_type', 'value', 'is_active',
                    'valid_from', 'valid_until']
    list_filter = ['discount_type', 'is_active']
    search_fields = ['name']


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ['product', 'product_name', 'unit_price', 'quantity',
                       'tax_amount', 'discount_amount', 'line_total']


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ['payment_method', 'amount', 'reference']


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['receipt_number', 'outlet', 'cashier_id', 'grand_total',
                    'status', 'created_at']
    list_filter = ['status', 'outlet']
    search_fields = ['receipt_number']
    inlines = [SaleItemInline, PaymentInline]


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ['id', 'outlet', 'user_id', 'status', 'opening_cash',
                    'closing_cash', 'expected_cash', 'opened_at', 'closed_at']
    list_filter = ['status', 'outlet']
