from django.contrib import admin
from .models import (
    Pump, Tank, TankReading, PumpReading,
    FuelDelivery, FuelReconciliation,
)


@admin.register(Pump)
class PumpAdmin(admin.ModelAdmin):
    list_display = ('pump_number', 'name', 'outlet', 'product', 'status')
    list_filter = ('status', 'outlet', 'product')
    search_fields = ('name', 'pump_number')


@admin.register(Tank)
class TankAdmin(admin.ModelAdmin):
    list_display = ('name', 'outlet', 'product', 'capacity', 'current_level', 'is_active')
    list_filter = ('is_active', 'outlet', 'product')
    search_fields = ('name',)


@admin.register(TankReading)
class TankReadingAdmin(admin.ModelAdmin):
    list_display = ('tank', 'reading_level', 'reading_type', 'reading_at')
    list_filter = ('reading_type', 'tank')
    date_hierarchy = 'reading_at'


@admin.register(PumpReading)
class PumpReadingAdmin(admin.ModelAdmin):
    list_display = ('pump', 'shift', 'opening_reading', 'closing_reading', 'volume_dispensed')
    list_filter = ('pump__outlet',)


@admin.register(FuelDelivery)
class FuelDeliveryAdmin(admin.ModelAdmin):
    list_display = ('tank', 'supplier', 'volume_received', 'total_cost', 'delivery_date')
    list_filter = ('tank__outlet', 'supplier')
    date_hierarchy = 'delivery_date'


@admin.register(FuelReconciliation)
class FuelReconciliationAdmin(admin.ModelAdmin):
    list_display = ('date', 'tank', 'outlet', 'variance', 'variance_type', 'status')
    list_filter = ('variance_type', 'status', 'outlet')
    date_hierarchy = 'date'
