from rest_framework import serializers
from .models import Account, FiscalPeriod, JournalEntry, JournalEntryLine, CashRequisition


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
    debit = serializers.DecimalField(max_digits=12, decimal_places=2, default=0, min_value=0)
    credit = serializers.DecimalField(max_digits=12, decimal_places=2, default=0, min_value=0)
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


class CashRequisitionSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()
    paid_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CashRequisition
        fields = '__all__'
        read_only_fields = [
            'requisition_number', 'requested_by_id', 'requested_at',
            'status', 'approval_request', 'approved_by_id', 'approved_at',
            'paid_by_id', 'paid_at', 'settled_amount', 'settled_at',
            'created_at', 'updated_at'
        ]

    def get_requested_by_name(self, obj):
        from users.models import User
        try:
            user = User.objects.get(id=obj.requested_by_id)
            return user.get_full_name() or user.username
        except User.DoesNotExist:
            return f"User #{obj.requested_by_id}"

    def get_approved_by_name(self, obj):
        if not obj.approved_by_id:
            return None
        from users.models import User
        try:
            user = User.objects.get(id=obj.approved_by_id)
            return user.get_full_name() or user.username
        except User.DoesNotExist:
            return f"User #{obj.approved_by_id}"

    def get_paid_by_name(self, obj):
        if not obj.paid_by_id:
            return None
        from users.models import User
        try:
            user = User.objects.get(id=obj.paid_by_id)
            return user.get_full_name() or user.username
        except User.DoesNotExist:
            return f"User #{obj.paid_by_id}"
