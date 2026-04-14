from django.contrib import admin
from .models import SystemConfig, ApprovalThreshold, AuditSetting


@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    list_display = ('business_name', 'currency_code', 'timezone', 'updated_at')

    def has_add_permission(self, request):
        # Singleton: prevent adding if one exists
        return not SystemConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ApprovalThreshold)
class ApprovalThresholdAdmin(admin.ModelAdmin):
    list_display = ('transaction_type', 'min_amount', 'max_amount', 'requires_role', 'is_active')
    list_filter = ('transaction_type', 'requires_role', 'is_active')


@admin.register(AuditSetting)
class AuditSettingAdmin(admin.ModelAdmin):
    list_display = ('log_type', 'is_enabled', 'retention_days')
    list_filter = ('is_enabled',)
