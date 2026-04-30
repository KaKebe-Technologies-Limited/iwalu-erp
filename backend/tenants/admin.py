from django.contrib import admin
from .models import (
    Client, Domain, TenantEmailVerification,
    SubscriptionPlan, TenantSubscription, SubscriptionInvoice
)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['name', 'schema_name', 'created_on']
    search_fields = ['name', 'schema_name']


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ['domain', 'tenant', 'is_primary']
    list_filter = ['is_primary']


@admin.register(TenantEmailVerification)
class TenantEmailVerificationAdmin(admin.ModelAdmin):
    list_display = ['email', 'tenant', 'created_at', 'used_at']
    list_filter = ['used_at']
    search_fields = ['email', 'tenant__name']


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'price_monthly', 'max_users', 'max_outlets', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(TenantSubscription)
class TenantSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'plan', 'billing_cycle', 'status', 'next_billing_date']
    list_filter = ['status', 'billing_cycle', 'plan']
    search_fields = ['tenant__name', 'plan__name']
    readonly_fields = ['trial_started_at', 'suspended_at']


@admin.register(SubscriptionInvoice)
class SubscriptionInvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'subscription', 'amount', 'status', 'due_date']
    list_filter = ['status', 'due_date']
    search_fields = ['invoice_number', 'subscription__tenant__name']
    readonly_fields = ['issued_at', 'paid_at']
