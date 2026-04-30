from django.contrib import admin
from .models import EfrisConfig, FiscalInvoice


@admin.register(EfrisConfig)
class EfrisConfigAdmin(admin.ModelAdmin):
    list_display = ('tin', 'legal_name', 'provider', 'is_enabled', 'updated_at')

    def has_add_permission(self, request):
        return not EfrisConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FiscalInvoice)
class FiscalInvoiceAdmin(admin.ModelAdmin):
    list_display = ('sale', 'status', 'provider', 'fdn', 'retry_count',
                    'submitted_at', 'accepted_at')
    list_filter = ('status', 'provider')
    search_fields = ('fdn', 'invoice_id', 'sale__receipt_number')
    readonly_fields = ('request_payload', 'response_payload',
                       'created_at', 'updated_at')
    date_hierarchy = 'created_at'
