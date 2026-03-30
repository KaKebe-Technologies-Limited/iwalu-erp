from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import (
    Employee, Attendance, LeaveBalance, LeaveRequest,
    PayrollPeriod, PaySlip, PaySlipLine,
)


def generate_employee_number():
    """Generate EMP-NNNN inside an atomic block."""
    last = (
        Employee.objects
        .select_for_update()
        .order_by('-employee_number')
        .first()
    )
    if last:
        try:
            last_num = int(last.employee_number.split('-')[-1])
            next_num = last_num + 1
        except (ValueError, IndexError):
            next_num = 1
    else:
        next_num = 1
    return f"EMP-{next_num:04d}"


# --- Attendance ---

def clock_in(employee, outlet=None):
    """Create attendance record for today."""
    today = timezone.now().date()
    if Attendance.objects.filter(employee=employee, date=today).exists():
        raise ValidationError({'attendance': 'Already clocked in today.'})

    return Attendance.objects.create(
        employee=employee,
        date=today,
        clock_in=timezone.now(),
        outlet=outlet,
    )


def clock_out(employee):
    """Close today's attendance record."""
    today = timezone.now().date()
    try:
        record = Attendance.objects.get(
            employee=employee, date=today, clock_out__isnull=True,
        )
    except Attendance.DoesNotExist:
        raise ValidationError({'attendance': 'No open attendance record for today.'})

    record.clock_out = timezone.now()
    record.save(update_fields=['clock_out', 'updated_at'])
    return record


# --- Leave ---

def submit_leave_request(employee, leave_type_id, start_date, end_date,
                         days_requested, reason=''):
    """Create a leave request after validating balance."""
    year = start_date.year
    balance = LeaveBalance.objects.filter(
        employee=employee, leave_type_id=leave_type_id, year=year,
    ).first()

    if balance and balance.remaining_days < days_requested:
        raise ValidationError({
            'leave': f'Insufficient leave balance. Remaining: {balance.remaining_days}, '
                     f'Requested: {days_requested}',
        })

    return LeaveRequest.objects.create(
        employee=employee,
        leave_type_id=leave_type_id,
        start_date=start_date,
        end_date=end_date,
        days_requested=days_requested,
        reason=reason,
    )


def approve_leave(leave_request, approver_id):
    """Approve a leave request and deduct from balance."""
    if leave_request.status != 'pending':
        raise ValidationError(
            {'status': f'Cannot approve a {leave_request.status} request.'}
        )

    with transaction.atomic():
        leave_request.status = 'approved'
        leave_request.approved_by = approver_id
        leave_request.approved_at = timezone.now()
        leave_request.save(update_fields=[
            'status', 'approved_by', 'approved_at', 'updated_at',
        ])

        # Deduct from balance
        year = leave_request.start_date.year
        balance, _ = LeaveBalance.objects.get_or_create(
            employee=leave_request.employee,
            leave_type=leave_request.leave_type,
            year=year,
            defaults={
                'entitled_days': leave_request.leave_type.days_per_year,
            },
        )
        balance.used_days += leave_request.days_requested
        balance.save(update_fields=['used_days'])

    return leave_request


def reject_leave(leave_request, approver_id, reason=''):
    """Reject a leave request."""
    if leave_request.status != 'pending':
        raise ValidationError(
            {'status': f'Cannot reject a {leave_request.status} request.'}
        )

    leave_request.status = 'rejected'
    leave_request.approved_by = approver_id
    leave_request.approved_at = timezone.now()
    leave_request.rejection_reason = reason
    leave_request.save(update_fields=[
        'status', 'approved_by', 'approved_at', 'rejection_reason', 'updated_at',
    ])
    return leave_request


# --- Payroll ---

# Uganda PAYE monthly brackets (effective 2023/2024)
PAYE_BRACKETS = [
    (Decimal('235000'), Decimal('0')),       # 0% up to 235,000
    (Decimal('335000'), Decimal('0.10')),     # 10% from 235,001 to 335,000
    (Decimal('410000'), Decimal('0.20')),     # 20% from 335,001 to 410,000
    (Decimal('10000000'), Decimal('0.30')),   # 30% from 410,001 to 10,000,000
    (None, Decimal('0.40')),                  # 40% above 10,000,000
]

NSSF_EMPLOYEE_RATE = Decimal('0.05')  # 5%
NSSF_EMPLOYER_RATE = Decimal('0.10')  # 10%


def calculate_paye(taxable_income):
    """Calculate Uganda PAYE using progressive monthly brackets."""
    tax = Decimal('0')
    previous_limit = Decimal('0')

    for limit, rate in PAYE_BRACKETS:
        if limit is None:
            # Top bracket — all remaining income
            tax += (taxable_income - previous_limit) * rate
            break
        if taxable_income <= limit:
            tax += (taxable_income - previous_limit) * rate
            break
        tax += (limit - previous_limit) * rate
        previous_limit = limit

    return tax.quantize(Decimal('1'))


def calculate_nssf(gross_salary):
    """Calculate NSSF contributions. Returns (employee, employer)."""
    employee = (gross_salary * NSSF_EMPLOYEE_RATE).quantize(Decimal('1'))
    employer = (gross_salary * NSSF_EMPLOYER_RATE).quantize(Decimal('1'))
    return employee, employer


def process_payroll(payroll_period, user_id):
    """Generate pay slips for all active employees."""
    if payroll_period.status not in ('draft', 'processing'):
        raise ValidationError(
            {'status': f'Cannot process a {payroll_period.status} payroll.'}
        )

    with transaction.atomic():
        # Clear any previous processing attempt
        payroll_period.pay_slips.all().delete()
        payroll_period.status = 'processing'
        payroll_period.processed_by = user_id
        payroll_period.save(update_fields=['status', 'processed_by', 'updated_at'])

        total_gross = Decimal('0')
        total_deductions = Decimal('0')
        total_net = Decimal('0')

        employees = Employee.objects.filter(employment_status='active')
        for employee in employees:
            gross = employee.basic_salary
            nssf_employee, nssf_employer = calculate_nssf(gross)
            taxable = gross - nssf_employee
            paye = calculate_paye(taxable)
            deductions = nssf_employee + paye
            net = gross - deductions

            pay_slip = PaySlip.objects.create(
                payroll_period=payroll_period,
                employee=employee,
                basic_salary=employee.basic_salary,
                gross_pay=gross,
                total_deductions=deductions,
                net_pay=net,
            )

            # Earnings
            PaySlipLine.objects.create(
                pay_slip=pay_slip,
                line_type='earning',
                description='Basic Salary',
                amount=gross,
            )

            # Deductions
            if nssf_employee > 0:
                PaySlipLine.objects.create(
                    pay_slip=pay_slip,
                    line_type='deduction',
                    description=f'NSSF Employee ({NSSF_EMPLOYEE_RATE * 100}%)',
                    amount=nssf_employee,
                )
            if paye > 0:
                PaySlipLine.objects.create(
                    pay_slip=pay_slip,
                    line_type='deduction',
                    description='PAYE',
                    amount=paye,
                )

            total_gross += gross
            total_deductions += deductions
            total_net += net

        payroll_period.total_gross = total_gross
        payroll_period.total_deductions = total_deductions
        payroll_period.total_net = total_net
        payroll_period.status = 'processing'
        payroll_period.save(update_fields=[
            'total_gross', 'total_deductions', 'total_net', 'status', 'updated_at',
        ])

    return payroll_period


def approve_payroll(payroll_period, approver_id):
    """Approve payroll and create journal entry."""
    if payroll_period.status != 'processing':
        raise ValidationError(
            {'status': f'Cannot approve a {payroll_period.status} payroll.'}
        )

    with transaction.atomic():
        # Calculate NSSF employer total
        total_nssf_employee = Decimal('0')
        total_nssf_employer = Decimal('0')
        total_paye = Decimal('0')

        for slip in payroll_period.pay_slips.select_related('employee').all():
            _, employer_nssf = calculate_nssf(slip.gross_pay)
            total_nssf_employer += employer_nssf
            for line in slip.lines.filter(line_type='deduction'):
                if 'NSSF' in line.description:
                    total_nssf_employee += line.amount
                elif 'PAYE' in line.description:
                    total_paye += line.amount

        # Create journal entry
        from finance.services import create_journal_entry
        from finance.models import Account

        def _account(code):
            return Account.objects.get(code=code, is_system=True).pk

        lines = [
            {
                'account_id': _account('5100'),
                'debit': payroll_period.total_gross,
                'credit': Decimal('0'),
                'description': 'Salary expense',
            },
            {
                'account_id': _account('5200'),
                'debit': total_nssf_employer,
                'credit': Decimal('0'),
                'description': 'NSSF employer contribution',
            },
            {
                'account_id': _account('2200'),
                'debit': Decimal('0'),
                'credit': total_nssf_employee + total_nssf_employer,
                'description': 'NSSF payable',
            },
            {
                'account_id': _account('2300'),
                'debit': Decimal('0'),
                'credit': total_paye,
                'description': 'PAYE payable',
            },
            {
                'account_id': _account('2400'),
                'debit': Decimal('0'),
                'credit': payroll_period.total_net,
                'description': 'Net salary payable',
            },
        ]

        # Remove zero-amount lines
        lines = [l for l in lines if l['debit'] > 0 or l['credit'] > 0]

        je = create_journal_entry(
            date=payroll_period.end_date,
            description=f'Payroll: {payroll_period.name}',
            lines_data=lines,
            source='payroll',
            reference_type='PayrollPeriod',
            reference_id=payroll_period.pk,
            created_by=approver_id,
            auto_post=True,
        )

        payroll_period.status = 'approved'
        payroll_period.approved_by = approver_id
        payroll_period.journal_entry = je
        payroll_period.save(update_fields=[
            'status', 'approved_by', 'journal_entry', 'updated_at',
        ])

    return payroll_period
