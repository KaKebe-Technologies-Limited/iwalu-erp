from rest_framework import serializers
from .models import SystemConfig, ApprovalThreshold, AuditSetting


class SystemConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemConfig
        fields = [
            'id', 'variance_tolerance_pct', 'low_stock_threshold_pct',
            'low_fuel_threshold_pct', 'business_name', 'tax_id',
            'currency_code', 'timezone', 'date_format',
            'receipt_header', 'receipt_footer',
            'enable_email_notifications', 'enable_sms_notifications',
            'created_at', 'updated_at',
        ]
        read_only_fields = ('id', 'created_at', 'updated_at')


class ApprovalThresholdSerializer(serializers.ModelSerializer):
    transaction_type_display = serializers.CharField(
        source='get_transaction_type_display', read_only=True,
    )
    requires_role_display = serializers.CharField(
        source='get_requires_role_display', read_only=True,
    )

    class Meta:
        model = ApprovalThreshold
        fields = [
            'id', 'transaction_type', 'transaction_type_display',
            'min_amount', 'max_amount',
            'requires_role', 'requires_role_display',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ('created_at', 'updated_at')

    def validate(self, data):
        min_amt = data.get('min_amount', getattr(self.instance, 'min_amount', None))
        max_amt = data.get('max_amount', getattr(self.instance, 'max_amount', None))
        if max_amt is not None and min_amt is not None and max_amt <= min_amt:
            raise serializers.ValidationError({
                'max_amount': 'Max amount must be greater than min amount.',
            })
        return data


class AuditSettingSerializer(serializers.ModelSerializer):
    log_type_display = serializers.CharField(
        source='get_log_type_display', read_only=True,
    )

    class Meta:
        model = AuditSetting
        fields = [
            'id', 'log_type', 'log_type_display',
            'is_enabled', 'retention_days',
            'created_at', 'updated_at',
        ]
        read_only_fields = ('created_at', 'updated_at')


class CheckApprovalSerializer(serializers.Serializer):
    transaction_type = serializers.ChoiceField(
        choices=ApprovalThreshold.TRANSACTION_TYPE_CHOICES,
    )
    amount = serializers.DecimalField(max_digits=15, decimal_places=2)
