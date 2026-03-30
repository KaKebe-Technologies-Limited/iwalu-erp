from django.contrib import admin
from .models import Account, FiscalPeriod, JournalEntry, JournalEntryLine


class JournalEntryLineInline(admin.TabularInline):
    model = JournalEntryLine
    extra = 0
    readonly_fields = ['account', 'debit', 'credit']


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'account_type', 'is_active', 'is_system']
    list_filter = ['account_type', 'is_active', 'is_system']
    search_fields = ['code', 'name']


@admin.register(FiscalPeriod)
class FiscalPeriodAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date', 'is_closed']
    list_filter = ['is_closed']


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ['entry_number', 'date', 'description', 'source', 'status']
    list_filter = ['status', 'source']
    search_fields = ['entry_number', 'description']
    inlines = [JournalEntryLineInline]

    def has_change_permission(self, request, obj=None):
        if obj and obj.status != 'draft':
            return False
        return super().has_change_permission(request, obj)
