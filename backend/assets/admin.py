from django.contrib import admin
from .models import AssetCategory, Asset, AssetAssignment, MaintenanceLog, AssetDisposal

@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'default_depreciation_method', 'default_useful_life_years', 'is_active')
    search_fields = ('name',)

class AssetAssignmentInline(admin.TabularInline):
    model = AssetAssignment
    extra = 0
    readonly_fields = ('created_at',)

class MaintenanceLogInline(admin.TabularInline):
    model = MaintenanceLog
    extra = 0

class AssetDisposalInline(admin.StackedInline):
    model = AssetDisposal
    extra = 0

@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('asset_code', 'name', 'category', 'status', 'cost', 'book_value')
    list_filter = ('category', 'status')
    search_fields = ('asset_code', 'name')
    inlines = [AssetAssignmentInline, MaintenanceLogInline, AssetDisposalInline]

@admin.register(AssetAssignment)
class AssetAssignmentAdmin(admin.ModelAdmin):
    list_display = ('asset', 'assigned_to_id', 'assigned_to_type', 'assigned_date', 'returned_date', 'is_current')
    list_filter = ('is_current', 'assigned_to_type')

@admin.register(MaintenanceLog)
class MaintenanceLogAdmin(admin.ModelAdmin):
    list_display = ('asset', 'maintenance_type', 'performed_date', 'cost', 'performed_by')
    list_filter = ('maintenance_type', 'performed_date')

@admin.register(AssetDisposal)
class AssetDisposalAdmin(admin.ModelAdmin):
    list_display = ('asset', 'disposal_date', 'disposal_method', 'proceeds', 'book_value_at_disposal')
