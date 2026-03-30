from django.contrib import admin
from .models import (
    Department, Employee, LeaveType, LeaveBalance,
    LeaveRequest, Attendance, PayrollPeriod, PaySlip, PaySlipLine,
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'outlet', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name']


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = [
        'employee_number', 'user_id', 'department', 'outlet',
        'employment_type', 'employment_status', 'basic_salary',
    ]
    list_filter = ['employment_type', 'employment_status', 'department']
    search_fields = ['employee_number', 'designation']


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'days_per_year', 'is_paid', 'is_active']


@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display = ['employee', 'leave_type', 'year', 'entitled_days', 'used_days']
    list_filter = ['year', 'leave_type']


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ['employee', 'leave_type', 'start_date', 'end_date', 'status']
    list_filter = ['status', 'leave_type']


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['employee', 'date', 'clock_in', 'clock_out', 'outlet']
    list_filter = ['date', 'outlet']


class PaySlipLineInline(admin.TabularInline):
    model = PaySlipLine
    extra = 0
    readonly_fields = ['line_type', 'description', 'amount']


class PaySlipInline(admin.TabularInline):
    model = PaySlip
    extra = 0
    readonly_fields = ['employee', 'basic_salary', 'gross_pay', 'total_deductions', 'net_pay']


@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date', 'status', 'total_gross', 'total_net']
    list_filter = ['status']
    inlines = [PaySlipInline]


@admin.register(PaySlip)
class PaySlipAdmin(admin.ModelAdmin):
    list_display = ['employee', 'payroll_period', 'gross_pay', 'total_deductions', 'net_pay']
    inlines = [PaySlipLineInline]
