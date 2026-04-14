from rest_framework import serializers
from .models import PaymentConfig, PaymentTransaction


class PaymentConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentConfig
        fields = [
            'id', 'is_enabled', 'default_provider', 'default_currency',
            # MTN
            'mtn_enabled', 'mtn_subscription_key', 'mtn_api_user', 'mtn_api_key',
            'mtn_base_url', 'mtn_target_environment', 'mtn_callback_url',
            # MTN Disbursement
            'mtn_disbursement_enabled', 'mtn_disbursement_subscription_key',
            'mtn_disbursement_api_user', 'mtn_disbursement_api_key',
            # Airtel
            'airtel_enabled', 'airtel_client_id', 'airtel_client_secret',
            'airtel_base_url', 'airtel_country', 'airtel_currency', 'airtel_callback_url',
            # Airtel Disbursement
            'airtel_disbursement_enabled', 'airtel_disbursement_client_id',
            'airtel_disbursement_client_secret',
            # Pesapal
            'pesapal_enabled', 'pesapal_consumer_key', 'pesapal_consumer_secret',
            'pesapal_base_url', 'pesapal_ipn_id', 'pesapal_callback_url',
            'created_at', 'updated_at',
        ]
        read_only_fields = ('id', 'created_at', 'updated_at')
        extra_kwargs = {
            'mtn_subscription_key': {'write_only': True},
            'mtn_api_user': {'write_only': True},
            'mtn_api_key': {'write_only': True},
            'mtn_disbursement_subscription_key': {'write_only': True},
            'mtn_disbursement_api_user': {'write_only': True},
            'mtn_disbursement_api_key': {'write_only': True},
            'airtel_client_id': {'write_only': True},
            'airtel_client_secret': {'write_only': True},
            'airtel_disbursement_client_id': {'write_only': True},
            'airtel_disbursement_client_secret': {'write_only': True},
            'pesapal_consumer_key': {'write_only': True},
            'pesapal_consumer_secret': {'write_only': True},
        }


class PaymentTransactionSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    method_display = serializers.CharField(source='get_method_display', read_only=True)
    provider_display = serializers.CharField(source='get_provider_display', read_only=True)
    transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)
    is_terminal = serializers.BooleanField(read_only=True)

    class Meta:
        model = PaymentTransaction
        fields = [
            'id', 'sale', 'transaction_type', 'transaction_type_display',
            'provider', 'provider_display',
            'method', 'method_display', 'status', 'status_display', 'is_terminal',
            'amount', 'currency', 'phone_number', 'customer_email', 'customer_name',
            'reference', 'description',
            'provider_transaction_id', 'provider_status_code', 'provider_status_message',
            'response_payload', 'error_message',
            'initiated_by', 'initiated_at', 'completed_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = [f for f in fields if f != 'id']


class InitiatePaymentSerializer(serializers.Serializer):
    """Inbound shape for POST /api/payments/initiate/."""
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=1)
    method = serializers.ChoiceField(
        choices=[c[0] for c in PaymentTransaction.METHOD_CHOICES],
    )
    provider = serializers.ChoiceField(
        choices=[c[0] for c in PaymentConfig.PROVIDER_CHOICES],
        required=False, allow_blank=True,
    )
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    customer_email = serializers.CharField(max_length=255, required=False, allow_blank=True)
    customer_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    description = serializers.CharField(max_length=255, required=False, allow_blank=True)
    sale_id = serializers.IntegerField(required=False, allow_null=True)
    currency = serializers.CharField(max_length=3, required=False, allow_blank=True)

    def validate(self, attrs):
        method = attrs.get('method')
        if method == 'mobile_money' and not attrs.get('phone_number'):
            raise serializers.ValidationError(
                {'phone_number': 'phone_number is required for mobile_money payments.'}
            )
        return attrs


class InitiateDisbursementSerializer(InitiatePaymentSerializer):
    """Inbound shape for POST /api/payments/disburse/."""
    # Disbursements are typically mobile_money only in this context
    method = serializers.ChoiceField(
        choices=[('mobile_money', 'Mobile Money')],
        default='mobile_money',
    )
