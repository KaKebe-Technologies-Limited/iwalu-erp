from django.contrib import admin
from .models import PaymentConfig, PaymentTransaction

@admin.register(PaymentConfig)
class PaymentConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_enabled', 'default_provider', 'default_currency', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('is_enabled', 'default_provider', 'default_currency')
        }),
        ('MTN MoMo', {
            'fields': (
                'mtn_enabled', 'mtn_subscription_key', 'mtn_api_user',
                'mtn_api_key', 'mtn_base_url', 'mtn_target_environment',
                'mtn_callback_url'
            ),
            'classes': ('collapse',),
        }),
        ('Airtel Money', {
            'fields': (
                'airtel_enabled', 'airtel_client_id', 'airtel_client_secret',
                'airtel_base_url', 'airtel_country', 'airtel_currency',
                'airtel_callback_url'
            ),
            'classes': ('collapse',),
        }),
        ('Pesapal', {
            'fields': (
                'pesapal_enabled', 'pesapal_consumer_key', 'pesapal_consumer_secret',
                'pesapal_base_url', 'pesapal_ipn_id', 'pesapal_callback_url'
            ),
            'classes': ('collapse',),
        }),
    )

@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'reference', 'provider', 'method', 'amount', 'currency',
        'status', 'created_at'
    )
    list_filter = ('status', 'provider', 'method', 'created_at')
    search_fields = ('reference', 'provider_transaction_id', 'phone_number', 'customer_email')
    readonly_fields = (
        'reference', 'provider_transaction_id', 'request_payload',
        'response_payload', 'callback_payload', 'created_at', 'updated_at'
    )
