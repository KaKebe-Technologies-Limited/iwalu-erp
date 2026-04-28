from decimal import Decimal
from rest_framework import serializers
from .models import (
    Department, Employee, LeaveType, LeaveBalance,
    LeaveRequest, Attendance, PayrollPeriod, PaySlip, PaySlipLine,
)


class DepartmentSerializer(serializers.ModelSerializer):
    outlet_name = serializers.CharField(source='outlet.name', read_only=True, default=None)
    employee_count = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = [
            'id', 'name', 'description', 'outlet', 'outlet_name',
            'is_active', 'employee_count', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_employee_count(self, obj):
        return obj.employees.filter(employment_status='active').count()


class EmployeeSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(
        source='department.name', read_only=True, default=None,
    )
    outlet_name = serializers.CharField(
        source='outlet.name', read_only=True, default=None,
    )

    class Meta:
        model = Employee
        fields = [
            'id', 'user_id', 'employee_number', 'department', 'department_name',
            'outlet', 'outlet_name', 'designation', 'employment_type',
            'employment_status', 'date_hired', 'date_terminated',
            'basic_salary', 'bank_name', 'bank_account',
            'mobile_money_number', 'nssf_number', 'tin_number',
            'emergency_contact_name', 'emergency_contact_phone',
            'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['employee_number', 'user_id', 'employment_status', 'created_at', 'updated_at']


class EmployeeCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = [
            'user_id', 'department', 'outlet', 'designation',
            'employment_type', 'date_hired', 'basic_salary',
            'bank_name', 'bank_account', 'mobile_money_number',
            'nssf_number', 'tin_number',
            'emergency_contact_name', 'emergency_contact_phone', 'notes',
        ]


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = [
            'id', 'name', 'days_per_year', 'is_paid', 'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class LeaveBalanceSerializer(serializers.ModelSerializer):
    employee_number = serializers.CharField(
        source='employee.employee_number', read_only=True,
    )
    leave_type_name = serializers.CharField(
        source='leave_type.name', read_only=True,
    )
    remaining_days = serializers.DecimalField(
        max_digits=5, decimal_places=1, read_only=True,
    )

    class Meta:
        model = LeaveBalance
        fields = [
            'id', 'employee', 'employee_number', 'leave_type',
            'leave_type_name', 'year', 'entitled_days', 'used_days',
            'carried_over', 'remaining_days',
        ]


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_number = serializers.CharField(
        source='employee.employee_number', read_only=True,
    )
    leave_type_name = serializers.CharField(
        source='leave_type.name', read_only=True,
    )

    class Meta:
        model = LeaveRequest
        fields = [
            'id', 'employee', 'employee_number', 'leave_type',
            'leave_type_name', 'start_date', 'end_date', 'days_requested',
            'reason', 'status', 'approval_request', 'approved_by', 'approved_at',
            'rejection_reason', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'status', 'approval_request', 'approved_by', 'approved_at',
            'rejection_reason', 'created_at', 'updated_at',
        ]


class LeaveRequestCreateSerializer(serializers.Serializer):
    leave_type = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    days_requested = serializers.DecimalField(max_digits=5, decimal_places=1, min_value=Decimal('0.5'))
    reason = serializers.CharField(required=False, default='')


class AttendanceSerializer(serializers.ModelSerializer):
    employee_number = serializers.CharField(
        source='employee.employee_number', read_only=True,
    )
    hours_worked = serializers.FloatField(read_only=True)

    class Meta:
        model = Attendance
        fields = [
            'id', 'employee', 'employee_number', 'date', 'clock_in',
            'clock_out', 'outlet', 'hours_worked', 'notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class PaySlipLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaySlipLine
        fields = ['id', 'line_type', 'description', 'amount']


class PaySlipSerializer(serializers.ModelSerializer):
    lines = PaySlipLineSerializer(many=True, read_only=True)
    employee_number = serializers.CharField(
        source='employee.employee_number', read_only=True,
    )

    class Meta:
        model = PaySlip
        fields = [
            'id', 'payroll_period', 'employee', 'employee_number',
            'basic_salary', 'gross_pay', 'total_deductions', 'net_pay',
            'lines', 'created_at',
        ]


class PayrollPeriodSerializer(serializers.ModelSerializer):
    pay_slips_count = serializers.SerializerMethodField()

    class Meta:
        model = PayrollPeriod
        fields = [
            'id', 'name', 'start_date', 'end_date', 'status',
            'processed_by', 'approved_by', 'approval_request', 'journal_entry',
            'total_gross', 'total_deductions', 'total_net',
            'pay_slips_count', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'status', 'processed_by', 'approved_by', 'approval_request', 'journal_entry',
            'total_gross', 'total_deductions', 'total_net',
            'created_at', 'updated_at',
        ]

    def get_pay_slips_count(self, obj):
        return obj.pay_slips.count()


class PayrollPeriodDetailSerializer(PayrollPeriodSerializer):
    pay_slips = PaySlipSerializer(many=True, read_only=True)

    class Meta(PayrollPeriodSerializer.Meta):
        fields = PayrollPeriodSerializer.Meta.fields + ['pay_slips']
