from django.contrib import admin
from .models import Outlet


@admin.register(Outlet)
class OutletAdmin(admin.ModelAdmin):
    list_display = ['name', 'outlet_type', 'phone', 'is_active', 'created_at']
    list_filter = ['outlet_type', 'is_active']
    search_fields = ['name', 'address']
