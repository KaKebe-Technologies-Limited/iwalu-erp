from rest_framework import serializers
from .models import EfrisConfig, FiscalInvoice


class EfrisConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = EfrisConfig
        fields = [
            'id', 'tin', 'legal_name', 'trade_name',
            'provider', 'is_enabled',
            'weaf_api_key', 'weaf_base_url',
            'default_currency', 'default_tax_rate',
            'created_at', 'updated_at',
        ]
        read_only_fields = ('id', 'created_at', 'updated_at')
        extra_kwargs = {
            # Write-only to avoid leaking the API key back in GET responses
            'weaf_api_key': {'write_only': True},
        }


class FiscalInvoiceSerializer(serializers.ModelSerializer):
    receipt_number = serializers.CharField(
        source='sale.receipt_number', read_only=True,
    )
    is_fiscalized = serializers.BooleanField(read_only=True)
    status_display = serializers.CharField(
        source='get_status_display', read_only=True,
    )

    class Meta:
        model = FiscalInvoice
        fields = [
            'id', 'sale', 'receipt_number',
            'status', 'status_display', 'is_fiscalized',
            'provider', 'fdn', 'invoice_id', 'verification_code', 'qr_code',
            'error_message', 'retry_count',
            'submitted_at', 'accepted_at', 'created_at', 'updated_at',
        ]
        read_only_fields = [f for f in fields if f != 'id']
