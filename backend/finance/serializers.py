from rest_framework import serializers
from .models import Account, FiscalPeriod, JournalEntry, JournalEntryLine


class AccountSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source='parent.name', read_only=True, default=None)
    outlet_name = serializers.CharField(source='outlet.name', read_only=True, default=None)
    children_count = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = [
            'id', 'code', 'name', 'account_type', 'parent', 'parent_name',
            'description', 'is_active', 'is_system', 'outlet', 'outlet_name',
            'children_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['is_system', 'created_at', 'updated_at']

    def get_children_count(self, obj):
        return obj.children.count()


class AccountCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = [
            'code', 'name', 'account_type', 'parent', 'description',
            'is_active', 'outlet',
        ]


class FiscalPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = FiscalPeriod
        fields = [
            'id', 'name', 'start_date', 'end_date', 'is_closed',
            'closed_by', 'closed_at', 'created_at', 'updated_at',
        ]
        read_only_fields = ['is_closed', 'closed_by', 'closed_at', 'created_at', 'updated_at']


class JournalEntryLineSerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source='account.code', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)

    class Meta:
        model = JournalEntryLine
        fields = [
            'id', 'account', 'account_code', 'account_name',
            'description', 'debit', 'credit', 'outlet',
        ]


class JournalEntryLineCreateSerializer(serializers.Serializer):
    account_id = serializers.IntegerField()
    description = serializers.CharField(required=False, default='')
    debit = serializers.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit = serializers.DecimalField(max_digits=12, decimal_places=2, default=0)
    outlet_id = serializers.IntegerField(required=False, allow_null=True)


class JournalEntrySerializer(serializers.ModelSerializer):
    lines = JournalEntryLineSerializer(many=True, read_only=True)
    fiscal_period_name = serializers.CharField(
        source='fiscal_period.name', read_only=True,
    )

    class Meta:
        model = JournalEntry
        fields = [
            'id', 'entry_number', 'date', 'fiscal_period', 'fiscal_period_name',
            'description', 'source', 'reference_type', 'reference_id',
            'status', 'created_by', 'posted_by', 'posted_at',
            'voided_by', 'voided_at', 'lines', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'entry_number', 'fiscal_period', 'status', 'created_by',
            'posted_by', 'posted_at', 'voided_by', 'voided_at',
            'created_at', 'updated_at',
        ]


class JournalEntryCreateSerializer(serializers.Serializer):
    date = serializers.DateField()
    description = serializers.CharField()
    lines = JournalEntryLineCreateSerializer(many=True)
