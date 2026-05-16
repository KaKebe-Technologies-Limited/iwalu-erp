# Phase 10 — Reports & Analytics Completion

**Branch**: `feat-phase-10-reports`  
**Depends on**: Phases 1–9 merged to `main`  
**Scope**: Backend only. Extends `reports/views.py` and `reports/urls.py` with HR/payroll reports, project performance reports, EFRIS tax compliance export, and a role-specific enhanced dashboard. No new models, no new app registration — `reports` is already in `TENANT_APPS`.

---

## Overview

The system proposal (section 18 "Reporting & Analytics") requires role-based dashboards with real-time KPIs, HR/payroll reports, project performance reports, and a tax compliance export for EFRIS. The `reports` app already provides sales, stock, shift, and a basic dashboard. This phase fills the remaining gaps entirely within `reports/views.py` and `reports/urls.py`.

This phase implements:

1. **HR headcount report** — employee count by department/status/type, date-range and department filterable.
2. **HR attendance summary** — total hours worked per employee or in aggregate, by period.
3. **HR leave summary** — leave balance, usage, and remaining days per employee and leave type.
4. **HR payroll summary** — payroll period totals with per-department breakdown.
5. **Project performance report** — all projects with budget/actual/variance, task counts, and status breakdown.
6. **Project time summary** — time entries by project and staff member, billable indicator, total hours.
7. **EFRIS/tax compliance export** — date-ranged sales joined with `FiscalInvoice`, returning FDN, receipt numbers, and tax amounts as JSON or CSV.
8. **Enhanced dashboard** — same URL (`/api/reports/dashboard/`) extended to return role-specific sections based on `request.user.role`.

**Key constraints carried forward from the existing codebase:**
- All views are function-based: `@api_view(['GET'])` + `@permission_classes([...])`, matching the existing pattern in `reports/views.py`.
- `_parse_dates(request)` helper already exists — reuse it on all date-filtered views.
- HR and project models live in tenant-scoped apps and use `IntegerField` for user/staff references (cross-schema FK restriction). Reports query these fields as plain integers; no `.select_related('user')` is possible.
- `FiscalInvoice` (in `fiscalization` app) has a `OneToOneField` to `sales.Sale`. Use `select_related('sale')` for the tax export.
- Tests use `TenantTestCase` + `TenantClient`.
- No migrations required — no new models.
- `LeaveBalance.remaining_days` is a Python `@property` (`entitled_days + carried_over - used_days`), not a DB column. Compute it in Python after fetching rows.
- `Attendance.hours_worked` is a Python `@property` computed from `clock_in`/`clock_out`. Compute in Python; use `ExpressionWrapper` for DB-level hour calculation only where needed for aggregation.
- `ProjectTimeEntry` uses `staff_id` (not `employee_id`) as the cross-schema user reference.
- `PaySlip` uses `gross_pay` and `net_pay` (not `gross_salary`/`net_salary`).

---

## URL Additions — `reports/urls.py`

Add the following eight paths to the existing `urlpatterns` list. The existing nine paths remain unchanged.

```python
from django.urls import path
from . import views

urlpatterns = [
    # --- Existing (unchanged) ---
    path('reports/sales-summary/', views.sales_summary, name='sales-summary'),
    path('reports/sales-by-outlet/', views.sales_by_outlet, name='sales-by-outlet'),
    path('reports/sales-by-product/', views.sales_by_product, name='sales-by-product'),
    path('reports/sales-by-payment-method/', views.sales_by_payment_method, name='sales-by-payment-method'),
    path('reports/hourly-sales/', views.hourly_sales, name='hourly-sales'),
    path('reports/stock-levels/', views.stock_levels, name='stock-levels'),
    path('reports/stock-movement/', views.stock_movement, name='stock-movement'),
    path('reports/shift-summary/', views.shift_summary, name='shift-summary'),
    path('reports/dashboard/', views.dashboard, name='reports-dashboard'),

    # --- Phase 10 additions ---
    path('reports/hr/headcount/', views.hr_headcount, name='hr-headcount'),
    path('reports/hr/attendance/', views.hr_attendance_summary, name='hr-attendance-summary'),
    path('reports/hr/leave/', views.hr_leave_summary, name='hr-leave-summary'),
    path('reports/hr/payroll/', views.hr_payroll_summary, name='hr-payroll-summary'),
    path('reports/projects/performance/', views.project_performance, name='project-performance'),
    path('reports/projects/time/', views.project_time_summary, name='project-time-summary'),
    path('reports/tax/efris-export/', views.tax_efris_export, name='tax-efris-export'),
]
```

> The `dashboard` path is NOT duplicated — the existing entry is updated in-place during Phase 8 of this plan. No new URL registration is needed for the dashboard.

---

## Phase 1: HR Headcount Report

### View: `hr_headcount`

Accepts `?department_id=`, `?employment_status=`, `?employment_type=`, `?date_from=`, `?date_to=`.  
The date range filters on `date_hired` — employees hired within the period.

Permission: `IsAdminOrManager | IsAccountantOrAbove` (HR data is sensitive; both admin/manager and accountant roles need it for audit purposes).

```python
@api_view(['GET'])
@permission_classes([(IsAdminOrManager | IsAccountantOrAbove)])
def hr_headcount(request):
    """
    GET /api/reports/hr/headcount/

    Returns employee count by department, employment_status, and employment_type.
    Optional filters:
      ?department_id=<int>        — restrict to one department
      ?employment_status=<str>    — active | on_leave | suspended | terminated
      ?employment_type=<str>      — full_time | part_time | contract | intern
      ?date_from=YYYY-MM-DD       — hired on or after
      ?date_to=YYYY-MM-DD         — hired on or before
    """
    from hr.models import Employee, Department

    date_from, date_to = _parse_dates(request)
    department_id = request.query_params.get('department_id')
    employment_status = request.query_params.get('employment_status')
    employment_type = request.query_params.get('employment_type')

    qs = Employee.objects.filter(
        date_hired__gte=date_from,
        date_hired__lte=date_to,
    )
    if department_id:
        qs = qs.filter(department_id=department_id)
    if employment_status:
        qs = qs.filter(employment_status=employment_status)
    if employment_type:
        qs = qs.filter(employment_type=employment_type)

    by_department = (
        qs
        .values('department', dept_name=F('department__name'))
        .annotate(count=Count('id'))
        .order_by('department__name')
    )

    by_status = (
        qs
        .values('employment_status')
        .annotate(count=Count('id'))
        .order_by('employment_status')
    )

    by_type = (
        qs
        .values('employment_type')
        .annotate(count=Count('id'))
        .order_by('employment_type')
    )

    return Response({
        'total': qs.count(),
        'by_department': list(by_department),
        'by_status': list(by_status),
        'by_type': list(by_type),
        'date_from': date_from.isoformat(),
        'date_to': date_to.isoformat(),
    })
```

**Why lazy import**: `hr` models are imported inside the view function. This avoids circular import issues since `reports` doesn't formally declare `hr` as a dependency — the tenant test runner resolves both at runtime. Use the same pattern for all Phase 10 views.

---

## Phase 2: HR Attendance Summary

### View: `hr_attendance_summary`

Returns total hours worked per employee within a period. `Attendance.hours_worked` is a Python property — compute hours at the DB layer using `ExpressionWrapper` with `F('clock_out') - F('clock_in')` cast to `DurationField`, then extract seconds.

Permission: `IsAdminOrManager | IsAccountantOrAbove`

```python
@api_view(['GET'])
@permission_classes([(IsAdminOrManager | IsAccountantOrAbove)])
def hr_attendance_summary(request):
    """
    GET /api/reports/hr/attendance/

    Returns attendance records with computed hours worked per employee.
    Optional filters:
      ?date_from=YYYY-MM-DD
      ?date_to=YYYY-MM-DD
      ?department_id=<int>
      ?employee_id=<int>
    """
    from django.db.models import ExpressionWrapper, DurationField, FloatField
    from django.db.models.functions import Extract
    from hr.models import Attendance, Employee

    date_from, date_to = _parse_dates(request)
    department_id = request.query_params.get('department_id')
    employee_id = request.query_params.get('employee_id')

    qs = Attendance.objects.filter(
        date__gte=date_from,
        date__lte=date_to,
        clock_out__isnull=False,  # Only completed shifts have hours
    ).select_related('employee', 'employee__department')

    if employee_id:
        qs = qs.filter(employee_id=employee_id)
    if department_id:
        qs = qs.filter(employee__department_id=department_id)

    # Compute duration at DB level to allow aggregation
    qs = qs.annotate(
        duration=ExpressionWrapper(
            F('clock_out') - F('clock_in'),
            output_field=DurationField(),
        )
    )

    # Aggregate hours per employee
    from collections import defaultdict
    employee_hours = defaultdict(float)
    employee_meta = {}

    for record in qs:
        emp_id = record.employee_id
        if record.duration:
            employee_hours[emp_id] += record.duration.total_seconds() / 3600
        if emp_id not in employee_meta:
            employee_meta[emp_id] = {
                'employee_id': emp_id,
                'employee_number': record.employee.employee_number,
                'designation': record.employee.designation,
                'department': record.employee.department.name if record.employee.department else None,
            }

    summary = []
    for emp_id, hours in sorted(employee_hours.items()):
        row = employee_meta[emp_id].copy()
        row['total_hours'] = round(hours, 2)
        summary.append(row)

    # Totals
    total_hours = sum(employee_hours.values())
    total_records = qs.count()

    return Response({
        'date_from': date_from.isoformat(),
        'date_to': date_to.isoformat(),
        'total_records': total_records,
        'total_hours': round(total_hours, 2),
        'employees': summary,
    })
```

---

## Phase 3: HR Leave Summary

### View: `hr_leave_summary`

Returns leave balances per employee and leave type. `remaining_days` is a computed property — fetch `entitled_days`, `carried_over`, `used_days` from the DB and compute the remainder in Python.

Permission: `IsAdminOrManager | IsAccountantOrAbove`

```python
@api_view(['GET'])
@permission_classes([(IsAdminOrManager | IsAccountantOrAbove)])
def hr_leave_summary(request):
    """
    GET /api/reports/hr/leave/

    Returns leave balance and usage per employee and leave type.
    Optional filters:
      ?employee_id=<int>
      ?department_id=<int>
      ?year=<int>           — defaults to current year

    Note: remaining_days = entitled_days + carried_over - used_days
          computed in Python (it is a model @property, not a DB column).
    """
    from hr.models import LeaveBalance

    employee_id = request.query_params.get('employee_id')
    department_id = request.query_params.get('department_id')
    year = request.query_params.get('year')

    try:
        year = int(year) if year else timezone.now().year
    except ValueError:
        year = timezone.now().year

    qs = LeaveBalance.objects.filter(
        year=year,
    ).select_related(
        'employee', 'employee__department', 'leave_type'
    )

    if employee_id:
        qs = qs.filter(employee_id=employee_id)
    if department_id:
        qs = qs.filter(employee__department_id=department_id)

    data = []
    for balance in qs.order_by('employee__employee_number', 'leave_type__name'):
        data.append({
            'employee_id': balance.employee_id,
            'employee_number': balance.employee.employee_number,
            'department': balance.employee.department.name if balance.employee.department else None,
            'leave_type': balance.leave_type.name,
            'is_paid': balance.leave_type.is_paid,
            'year': balance.year,
            'entitled_days': str(balance.entitled_days),
            'carried_over': str(balance.carried_over),
            'used_days': str(balance.used_days),
            'remaining_days': str(balance.remaining_days),  # @property
        })

    return Response({
        'year': year,
        'count': len(data),
        'balances': data,
    })
```

---

## Phase 4: HR Payroll Summary

### View: `hr_payroll_summary`

Returns `PayrollPeriod` totals and a per-department breakdown of `PaySlip` sums.

Permission: `IsAdminOrManager | IsAccountantOrAbove`

```python
@api_view(['GET'])
@permission_classes([(IsAdminOrManager | IsAccountantOrAbove)])
def hr_payroll_summary(request):
    """
    GET /api/reports/hr/payroll/

    Returns payroll period totals and per-department breakdown.
    Optional filters:
      ?date_from=YYYY-MM-DD    — period start_date >= date_from
      ?date_to=YYYY-MM-DD      — period end_date <= date_to
      ?status=<str>            — draft | pending_approval | processing | approved | paid | rejected
      ?department_id=<int>     — restrict breakdown to one department

    PaySlip fields used: gross_pay, net_pay, total_deductions
    PayrollPeriod fields: total_gross, total_deductions, total_net
    """
    from hr.models import PayrollPeriod, PaySlip

    date_from, date_to = _parse_dates(request)
    status_filter = request.query_params.get('status')
    department_id = request.query_params.get('department_id')

    periods = PayrollPeriod.objects.filter(
        start_date__gte=date_from,
        end_date__lte=date_to,
    )
    if status_filter:
        periods = periods.filter(status=status_filter)

    periods_data = list(periods.values(
        'id', 'name', 'start_date', 'end_date', 'status',
        'total_gross', 'total_deductions', 'total_net',
    ).order_by('-start_date'))

    # Per-department breakdown across all matching periods
    payslip_qs = PaySlip.objects.filter(
        payroll_period__in=periods,
    ).select_related('employee', 'employee__department')

    if department_id:
        payslip_qs = payslip_qs.filter(employee__department_id=department_id)

    dept_totals = (
        payslip_qs
        .values(
            dept_id=F('employee__department'),
            dept_name=F('employee__department__name'),
        )
        .annotate(
            headcount=Count('id'),
            total_gross=Sum('gross_pay'),
            total_deductions=Sum('total_deductions'),
            total_net=Sum('net_pay'),
        )
        .order_by('dept_name')
    )

    # Overall aggregates across all matching periods
    overall = periods.aggregate(
        total_gross=Sum('total_gross'),
        total_deductions=Sum('total_deductions'),
        total_net=Sum('total_net'),
    )
    for key in overall:
        if overall[key] is None:
            overall[key] = Decimal('0.00')

    return Response({
        'date_from': date_from.isoformat(),
        'date_to': date_to.isoformat(),
        'period_count': len(periods_data),
        'overall': overall,
        'periods': periods_data,
        'by_department': list(dept_totals),
    })
```

---

## Phase 5: Project Performance Report

### View: `project_performance`

Returns all projects with budget, actual cost, variance, budget utilisation percentage, and task counts by status.

Permission: `IsAdminOrManager`

```python
@api_view(['GET'])
@permission_classes([IsAdminOrManager])
def project_performance(request):
    """
    GET /api/reports/projects/performance/

    Returns projects with budget/actual/variance and task status breakdown.
    Optional filters:
      ?status=<str>          — draft | pending_approval | active | on_hold | completed | cancelled
      ?date_from=YYYY-MM-DD  — project start_date >= date_from
      ?date_to=YYYY-MM-DD    — project start_date <= date_to
      ?project_id=<int>      — single project detail

    Project fields: name, status, budget, actual_cost, start_date, end_date, manager_id
    budget_variance = budget - actual_cost (positive = under budget)
    budget_utilisation_pct = actual_cost / budget * 100
    """
    from projects.models import Project, ProjectTask

    date_from, date_to = _parse_dates(request)
    status_filter = request.query_params.get('status')
    project_id = request.query_params.get('project_id')

    qs = Project.objects.filter(
        start_date__gte=date_from,
        start_date__lte=date_to,
    )
    if status_filter:
        qs = qs.filter(status=status_filter)
    if project_id:
        qs = qs.filter(pk=project_id)

    # Task counts per project per status — build a lookup to avoid N+1
    task_counts = (
        ProjectTask.objects
        .filter(project__in=qs)
        .values('project_id', 'status')
        .annotate(count=Count('id'))
    )
    # Build dict: {project_id: {status: count}}
    task_map = {}
    for row in task_counts:
        task_map.setdefault(row['project_id'], {})[row['status']] = row['count']

    data = []
    for project in qs.order_by('-start_date'):
        budget = project.budget
        actual = project.actual_cost
        variance = budget - actual
        utilisation_pct = (
            (actual / budget * 100).quantize(Decimal('0.01'))
            if budget > 0 else Decimal('0.00')
        )
        tasks = task_map.get(project.id, {})
        total_tasks = sum(tasks.values())

        data.append({
            'id': project.id,
            'project_number': project.project_number,
            'name': project.name,
            'status': project.status,
            'manager_id': project.manager_id,
            'start_date': project.start_date.isoformat(),
            'end_date': project.end_date.isoformat() if project.end_date else None,
            'budget': str(budget),
            'actual_cost': str(actual),
            'budget_variance': str(variance),
            'budget_utilisation_pct': str(utilisation_pct),
            'is_over_budget': actual > budget,
            'task_counts': {
                'total': total_tasks,
                'todo': tasks.get('todo', 0),
                'in_progress': tasks.get('in_progress', 0),
                'blocked': tasks.get('blocked', 0),
                'done': tasks.get('done', 0),
                'cancelled': tasks.get('cancelled', 0),
            },
        })

    # Summary aggregates
    summary = qs.aggregate(
        total_budget=Sum('budget'),
        total_actual=Sum('actual_cost'),
    )
    total_budget = summary['total_budget'] or Decimal('0.00')
    total_actual = summary['total_actual'] or Decimal('0.00')

    return Response({
        'date_from': date_from.isoformat(),
        'date_to': date_to.isoformat(),
        'project_count': len(data),
        'summary': {
            'total_budget': str(total_budget),
            'total_actual_cost': str(total_actual),
            'total_variance': str(total_budget - total_actual),
        },
        'projects': data,
    })
```

---

## Phase 6: Project Time Summary

### View: `project_time_summary`

Returns time entry totals by project and staff member.

**Note on `is_billable`**: `ProjectTimeEntry` does not have an `is_billable` field in the current model. The response omits billable/non-billable split. If billable tracking is added later, add a `BooleanField(default=False)` to the model and a migration — this plan does not add it to keep scope clean.

Permission: `IsAdminOrManager`

```python
@api_view(['GET'])
@permission_classes([IsAdminOrManager])
def project_time_summary(request):
    """
    GET /api/reports/projects/time/

    Returns time entries grouped by project and staff_id.
    Optional filters:
      ?date_from=YYYY-MM-DD
      ?date_to=YYYY-MM-DD
      ?project_id=<int>
      ?staff_id=<int>        — matches ProjectTimeEntry.staff_id

    ProjectTimeEntry fields: project, staff_id, date, hours, description
    Note: staff_id is a plain IntegerField — no user lookup is possible here.
          The frontend must resolve staff names from /api/users/ if needed.
    """
    from projects.models import ProjectTimeEntry, Project

    date_from, date_to = _parse_dates(request)
    project_id = request.query_params.get('project_id')
    staff_id = request.query_params.get('staff_id')

    qs = ProjectTimeEntry.objects.filter(
        date__gte=date_from,
        date__lte=date_to,
    ).select_related('project')

    if project_id:
        qs = qs.filter(project_id=project_id)
    if staff_id:
        qs = qs.filter(staff_id=staff_id)

    # Group by project + staff
    by_project_staff = (
        qs
        .values(
            'project_id',
            project_number=F('project__project_number'),
            project_name=F('project__name'),
            project_status=F('project__status'),
            'staff_id',
        )
        .annotate(
            total_hours=Sum('hours'),
            entry_count=Count('id'),
        )
        .order_by('project__project_number', 'staff_id')
    )

    # Per-project totals
    by_project = (
        qs
        .values(
            'project_id',
            project_number=F('project__project_number'),
            project_name=F('project__name'),
        )
        .annotate(
            total_hours=Sum('hours'),
            entry_count=Count('id'),
            staff_count=Count('staff_id', distinct=True),
        )
        .order_by('project__project_number')
    )

    overall = qs.aggregate(
        total_hours=Sum('hours'),
        entry_count=Count('id'),
    )

    return Response({
        'date_from': date_from.isoformat(),
        'date_to': date_to.isoformat(),
        'total_hours': str(overall['total_hours'] or Decimal('0.00')),
        'total_entries': overall['entry_count'] or 0,
        'by_project': list(by_project),
        'by_project_and_staff': list(by_project_staff),
    })
```

---

## Phase 7: EFRIS/Tax Compliance Export

### View: `tax_efris_export`

Joins `Sale` with `FiscalInvoice` for a date range. Supports `?format=csv` for spreadsheet-friendly export. Uses Python `csv` module and returns `HttpResponse` with `content_type='text/csv'`.

Permission: `IsAdminOrManager | IsAccountantOrAbove`

```python
@api_view(['GET'])
@permission_classes([(IsAdminOrManager | IsAccountantOrAbove)])
def tax_efris_export(request):
    """
    GET /api/reports/tax/efris-export/

    Returns sale records with their EFRIS fiscal status and FDN for tax compliance.
    Optional filters:
      ?date_from=YYYY-MM-DD
      ?date_to=YYYY-MM-DD
      ?status=<str>         — accepted | rejected | pending | failed | skipped
      ?outlet=<int>         — outlet_id
      ?format=csv           — returns text/csv attachment instead of JSON

    FiscalInvoice fields used: fdn, status, submitted_at, verification_code, invoice_id
    Sale fields used: receipt_number, grand_total, tax_total, created_at, outlet

    Sales without a FiscalInvoice row are included with status='no_submission'.
    """
    import csv as csv_module
    from django.http import HttpResponse
    from fiscalization.models import FiscalInvoice

    date_from, date_to = _parse_dates(request)
    status_filter = request.query_params.get('status')
    outlet_filter = request.query_params.get('outlet')
    export_format = request.query_params.get('format', 'json').lower()

    # Base sale queryset
    sales_qs = Sale.objects.filter(
        status='completed',
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
    ).select_related('fiscal_invoice')

    if outlet_filter:
        sales_qs = sales_qs.filter(outlet_id=outlet_filter)

    # Apply fiscal status filter
    if status_filter:
        if status_filter == 'no_submission':
            sales_qs = sales_qs.filter(fiscal_invoice__isnull=True)
        else:
            sales_qs = sales_qs.filter(fiscal_invoice__status=status_filter)

    rows = []
    for sale in sales_qs.order_by('created_at'):
        fiscal = getattr(sale, 'fiscal_invoice', None)
        rows.append({
            'sale_id': sale.id,
            'receipt_number': sale.receipt_number,
            'sale_date': sale.created_at.date().isoformat(),
            'sale_time': sale.created_at.strftime('%H:%M:%S'),
            'outlet_id': sale.outlet_id,
            'grand_total': str(sale.grand_total),
            'tax_total': str(sale.tax_total),
            'fiscal_status': fiscal.status if fiscal else 'no_submission',
            'fdn': fiscal.fdn if fiscal else '',
            'invoice_id': fiscal.invoice_id if fiscal else '',
            'verification_code': fiscal.verification_code if fiscal else '',
            'submitted_at': (
                fiscal.submitted_at.isoformat() if fiscal and fiscal.submitted_at else ''
            ),
            'accepted_at': (
                fiscal.accepted_at.isoformat() if fiscal and fiscal.accepted_at else ''
            ),
        })

    if export_format == 'csv':
        response = HttpResponse(content_type='text/csv')
        filename = (
            f'efris-export-{date_from.isoformat()}-to-{date_to.isoformat()}.csv'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        if rows:
            fieldnames = list(rows[0].keys())
            writer = csv_module.DictWriter(response, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        return response

    # JSON response
    totals = {
        'total_sales': len(rows),
        'total_grand': str(
            sum(Decimal(r['grand_total']) for r in rows) or Decimal('0.00')
        ),
        'total_tax': str(
            sum(Decimal(r['tax_total']) for r in rows) or Decimal('0.00')
        ),
        'accepted_count': sum(1 for r in rows if r['fiscal_status'] == 'accepted'),
        'pending_count': sum(1 for r in rows if r['fiscal_status'] == 'pending'),
        'rejected_count': sum(1 for r in rows if r['fiscal_status'] == 'rejected'),
        'no_submission_count': sum(1 for r in rows if r['fiscal_status'] == 'no_submission'),
    }

    return Response({
        'date_from': date_from.isoformat(),
        'date_to': date_to.isoformat(),
        'summary': totals,
        'records': rows,
    })
```

---

## Phase 8: Enhanced Role-Based Dashboard

The existing `dashboard` view returns the same four KPIs regardless of user role. Replace it with a version that returns role-specific sections. The URL and function name remain unchanged — no URL registration change needed.

**Role sections:**
- `cashier` / `attendant` — today's shift sales only (existing behaviour, unchanged)
- `manager` — sales KPIs + active shifts + low stock + top 5 products today
- `admin` — everything manager sees + payroll summary + HR headcount
- `accountant` — today's revenue, tax collected, pending EFRIS submissions

Replace the existing `dashboard` function in `reports/views.py`:

```python
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard(request):
    """
    GET /api/reports/dashboard/

    Role-specific KPI dashboard.
    Role sections:
      cashier / attendant  — shift-scoped: today sales, today revenue
      manager              — outlet-scoped (or all): sales, shifts, stock, top products
      admin                — manager section + HR headcount + payroll total
      accountant           — revenue, tax collected, pending EFRIS count
    All sections accept ?outlet=<id> to scope to one outlet (ignored for cashier/attendant).
    """
    from fiscalization.models import FiscalInvoice
    from hr.models import Employee, PayrollPeriod

    today = timezone.now().date()
    outlet = request.query_params.get('outlet')
    user = request.user

    # --- cashier / attendant: shift-scoped view (existing behaviour) ---
    if user.role in ('cashier', 'attendant'):
        current_shift = Shift.objects.filter(
            user_id=user.id, status='open',
        ).first()
        if current_shift:
            outlet = str(current_shift.outlet_id)
        else:
            return Response({
                'role': user.role,
                'today_sales': 0,
                'today_revenue': Decimal('0.00'),
                'active_shifts': 0,
                'low_stock_count': 0,
            })

        sales = _filter_sales(today, today, outlet)
        totals = sales.aggregate(
            today_sales=Count('id'),
            today_revenue=Sum('grand_total'),
        )
        active_shifts = Shift.objects.filter(status='open', outlet_id=outlet).count()
        return Response({
            'role': user.role,
            'today_sales': totals['today_sales'] or 0,
            'today_revenue': totals['today_revenue'] or Decimal('0.00'),
            'active_shifts': active_shifts,
            'low_stock_count': 0,
            'date': today.isoformat(),
        })

    # --- Shared sales KPIs (manager, admin, accountant) ---
    sales = _filter_sales(today, today, outlet)
    totals = sales.aggregate(
        today_sales=Count('id'),
        today_revenue=Sum('grand_total'),
        today_tax=Sum('tax_total'),
    )
    today_sales = totals['today_sales'] or 0
    today_revenue = totals['today_revenue'] or Decimal('0.00')
    today_tax = totals['today_tax'] or Decimal('0.00')

    active_shifts_qs = Shift.objects.filter(status='open')
    if outlet:
        active_shifts_qs = active_shifts_qs.filter(outlet_id=outlet)
    active_shifts = active_shifts_qs.count()

    low_stock_count = Product.objects.filter(
        track_stock=True, is_active=True,
        stock_quantity__lte=F('reorder_level'),
    ).count()

    # --- accountant ---
    if user.role == 'accountant':
        pending_efris = FiscalInvoice.objects.filter(
            status__in=['pending', 'submitted', 'failed']
        ).count()
        return Response({
            'role': user.role,
            'today_sales': today_sales,
            'today_revenue': today_revenue,
            'today_tax_collected': today_tax,
            'pending_efris_submissions': pending_efris,
            'active_shifts': active_shifts,
            'date': today.isoformat(),
        })

    # --- manager base section ---
    top_products = (
        SaleItem.objects
        .filter(
            sale__status='completed',
            sale__created_at__date=today,
        )
        .values('product', product_name=F('product__name'))
        .annotate(total_revenue=Sum('line_total'), total_qty=Sum('quantity'))
        .order_by('-total_revenue')[:5]
    )
    if outlet:
        top_products = top_products.filter(sale__outlet_id=outlet)

    manager_section = {
        'role': user.role,
        'today_sales': today_sales,
        'today_revenue': today_revenue,
        'today_tax_collected': today_tax,
        'active_shifts': active_shifts,
        'low_stock_count': low_stock_count,
        'top_products_today': list(top_products),
        'date': today.isoformat(),
    }

    if user.role == 'manager':
        return Response(manager_section)

    # --- admin: manager section + HR overview ---
    active_employee_count = Employee.objects.filter(
        employment_status='active'
    ).count()

    # Latest approved/paid payroll period
    latest_payroll = (
        PayrollPeriod.objects
        .filter(status__in=['approved', 'paid'])
        .order_by('-end_date')
        .values('name', 'end_date', 'total_gross', 'total_net', 'status')
        .first()
    )

    admin_section = manager_section.copy()
    admin_section.update({
        'role': 'admin',
        'active_employees': active_employee_count,
        'latest_payroll': latest_payroll,
    })
    return Response(admin_section)
```

---

## Phase 9: Tests — `reports/tests_phase10.py`

Create a new test file `backend/reports/tests_phase10.py`. All tests use `TenantTestCase` + `TenantClient`.

```python
from decimal import Decimal

from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from rest_framework import status

from outlets.models import Outlet
from products.models import Category, Product
from sales.models import Sale, SaleItem, Payment, Shift
from hr.models import (
    Department, Employee, LeaveType, LeaveBalance,
    LeaveRequest, Attendance, PayrollPeriod, PaySlip,
)
from projects.models import Project, ProjectTask, ProjectTimeEntry, ProjectExpense
from fiscalization.models import FiscalInvoice
from users.models import User


class ReportsPhase10TestCase(TenantTestCase):
    """
    Base class. Creates shared fixtures once per test class.
    Uses setUpTestData for performance; individual tests use setUp for TenantClient.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.outlet = Outlet.objects.create(name='Test Station', outlet_type='fuel_station')

        # Users
        cls.admin = User.objects.create_user(
            email='admin@test.com', password='pass123', role='admin'
        )
        cls.manager = User.objects.create_user(
            email='manager@test.com', password='pass123', role='manager'
        )
        cls.cashier = User.objects.create_user(
            email='cashier@test.com', password='pass123', role='cashier'
        )
        cls.accountant = User.objects.create_user(
            email='accountant@test.com', password='pass123', role='accountant'
        )

        # HR fixtures
        cls.dept = Department.objects.create(name='Operations', outlet=cls.outlet)
        cls.dept2 = Department.objects.create(name='Finance')
        cls.employee = Employee.objects.create(
            user_id=cls.cashier.id,
            employee_number='EMP-001',
            department=cls.dept,
            outlet=cls.outlet,
            designation='Cashier',
            employment_type='full_time',
            employment_status='active',
            date_hired='2025-01-01',
            basic_salary=Decimal('800000'),
        )
        cls.employee2 = Employee.objects.create(
            user_id=cls.accountant.id,
            employee_number='EMP-002',
            department=cls.dept2,
            designation='Accountant',
            employment_type='full_time',
            employment_status='active',
            date_hired='2025-03-01',
            basic_salary=Decimal('1200000'),
        )
        cls.leave_type = LeaveType.objects.create(
            name='Annual Leave', days_per_year=21, is_paid=True, is_active=True
        )
        cls.leave_balance = LeaveBalance.objects.create(
            employee=cls.employee,
            leave_type=cls.leave_type,
            year=2026,
            entitled_days=Decimal('21'),
            used_days=Decimal('5'),
            carried_over=Decimal('2'),
        )

        # Products & sales
        cls.category = Category.objects.create(
            name='Fuel', business_unit='fuel_station', is_active=True
        )
        cls.product = Product.objects.create(
            name='Petrol',
            sku='PTL-001',
            category=cls.category,
            selling_price=Decimal('5000'),
            tax_rate=Decimal('18.00'),
            track_stock=True,
            stock_quantity=Decimal('1000'),
            reorder_level=Decimal('100'),
            unit='litre',
            is_active=True,
        )
        cls.shift = Shift.objects.create(
            outlet=cls.outlet,
            user_id=cls.cashier.id,
            status='closed',
            opening_cash=Decimal('50000'),
            closing_cash=Decimal('50000'),
        )
        cls.sale = Sale.objects.create(
            outlet=cls.outlet,
            shift=cls.shift,
            cashier_id=cls.cashier.id,
            receipt_number='S001-2026-0001',
            subtotal=Decimal('50000.00'),
            tax_total=Decimal('9000.00'),
            discount_total=Decimal('0.00'),
            grand_total=Decimal('59000.00'),
            status='completed',
        )
        cls.sale_item = SaleItem.objects.create(
            sale=cls.sale,
            product=cls.product,
            product_name='Petrol',
            unit_price=Decimal('5000'),
            quantity=Decimal('10'),
            tax_rate=Decimal('18.00'),
            tax_amount=Decimal('9000.00'),
            discount_amount=Decimal('0.00'),
            line_total=Decimal('59000.00'),
        )
        cls.payment = Payment.objects.create(
            sale=cls.sale,
            payment_method='cash',
            amount=Decimal('59000.00'),
        )
        cls.fiscal_invoice = FiscalInvoice.objects.create(
            sale=cls.sale,
            status='accepted',
            provider='mock',
            fdn='FDN-2026-001',
            invoice_id='INV-001',
            verification_code='VER-001',
        )

        # Payroll
        cls.payroll_period = PayrollPeriod.objects.create(
            name='May 2026',
            start_date='2026-05-01',
            end_date='2026-05-31',
            status='paid',
            total_gross=Decimal('2000000'),
            total_deductions=Decimal('400000'),
            total_net=Decimal('1600000'),
        )
        cls.payslip = PaySlip.objects.create(
            payroll_period=cls.payroll_period,
            employee=cls.employee,
            basic_salary=Decimal('800000'),
            gross_pay=Decimal('900000'),
            total_deductions=Decimal('180000'),
            net_pay=Decimal('720000'),
        )

        # Projects
        cls.project = Project.objects.create(
            project_number='PRJ-20260101-0001',
            name='Pump Upgrade',
            status='active',
            manager_id=cls.manager.id,
            start_date='2026-01-01',
            end_date='2026-06-30',
            budget=Decimal('10000000'),
            actual_cost=Decimal('6000000'),
        )
        cls.task = ProjectTask.objects.create(
            project=cls.project,
            title='Install Pump A',
            status='done',
            priority='high',
            created_by_id=cls.manager.id,
        )
        cls.task2 = ProjectTask.objects.create(
            project=cls.project,
            title='Install Pump B',
            status='in_progress',
            priority='medium',
            created_by_id=cls.manager.id,
        )
        cls.time_entry = ProjectTimeEntry.objects.create(
            project=cls.project,
            staff_id=cls.cashier.id,
            date='2026-05-01',
            hours=Decimal('8.00'),
            description='On-site installation',
        )

    def setUp(self):
        self.client = TenantClient(self.tenant)

    def _auth(self, user):
        """Force-authenticate and return for chaining."""
        self.client.force_authenticate(user=user)


# ---------------------------------------------------------------------------
# Group 1: hr_headcount (5 tests)
# ---------------------------------------------------------------------------

class HRHeadcountTests(ReportsPhase10TestCase):

    def setUp(self):
        super().setUp()
        self.url = '/api/reports/hr/headcount/'

    def test_admin_can_access(self):
        self._auth(self.admin)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_accountant_can_access(self):
        self._auth(self.accountant)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_cashier_forbidden(self):
        self._auth(self.cashier)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_response_structure(self):
        self._auth(self.admin)
        resp = self.client.get(self.url + '?date_from=2025-01-01&date_to=2026-12-31')
        self.assertIn('total', resp.data)
        self.assertIn('by_department', resp.data)
        self.assertIn('by_status', resp.data)
        self.assertIn('by_type', resp.data)

    def test_department_filter(self):
        self._auth(self.admin)
        resp = self.client.get(
            self.url + f'?date_from=2025-01-01&date_to=2026-12-31&department_id={self.dept.id}'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Only cls.employee is in dept, not cls.employee2
        self.assertEqual(resp.data['total'], 1)


# ---------------------------------------------------------------------------
# Group 2: hr_attendance_summary (5 tests)
# ---------------------------------------------------------------------------

class HRAttendanceTests(ReportsPhase10TestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from django.utils import timezone
        import datetime
        # Create attendance records
        base_dt = timezone.make_aware(datetime.datetime(2026, 5, 10, 8, 0, 0))
        cls.attendance = Attendance.objects.create(
            employee=cls.employee,
            date='2026-05-10',
            clock_in=base_dt,
            clock_out=base_dt.replace(hour=16),  # 8 hours
        )

    def setUp(self):
        super().setUp()
        self.url = '/api/reports/hr/attendance/'

    def test_admin_can_access(self):
        self._auth(self.admin)
        resp = self.client.get(self.url + '?date_from=2026-05-01&date_to=2026-05-31')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_cashier_forbidden(self):
        self._auth(self.cashier)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_response_has_employees_list(self):
        self._auth(self.admin)
        resp = self.client.get(self.url + '?date_from=2026-05-01&date_to=2026-05-31')
        self.assertIn('employees', resp.data)
        self.assertIn('total_hours', resp.data)

    def test_hours_calculated_correctly(self):
        self._auth(self.admin)
        resp = self.client.get(self.url + '?date_from=2026-05-01&date_to=2026-05-31')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # cls.attendance has 8 hours; check total_hours >= 8.0
        self.assertGreaterEqual(float(resp.data['total_hours']), 8.0)

    def test_employee_filter(self):
        self._auth(self.admin)
        resp = self.client.get(
            self.url + f'?date_from=2026-05-01&date_to=2026-05-31&employee_id={self.employee.id}'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for emp in resp.data['employees']:
            self.assertEqual(emp['employee_id'], self.employee.id)


# ---------------------------------------------------------------------------
# Group 3: hr_leave_summary (5 tests)
# ---------------------------------------------------------------------------

class HRLeaveSummaryTests(ReportsPhase10TestCase):

    def setUp(self):
        super().setUp()
        self.url = '/api/reports/hr/leave/'

    def test_admin_can_access(self):
        self._auth(self.admin)
        resp = self.client.get(self.url + '?year=2026')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_accountant_can_access(self):
        self._auth(self.accountant)
        resp = self.client.get(self.url + '?year=2026')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_cashier_forbidden(self):
        self._auth(self.cashier)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_balance_fields_present(self):
        self._auth(self.admin)
        resp = self.client.get(self.url + '?year=2026')
        self.assertIn('balances', resp.data)
        if resp.data['balances']:
            row = resp.data['balances'][0]
            for field in ('entitled_days', 'used_days', 'remaining_days', 'carried_over'):
                self.assertIn(field, row)

    def test_remaining_days_computed_correctly(self):
        """remaining_days = entitled_days + carried_over - used_days = 21 + 2 - 5 = 18"""
        self._auth(self.admin)
        resp = self.client.get(
            self.url + f'?year=2026&employee_id={self.employee.id}'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['balances']), 1)
        self.assertEqual(Decimal(resp.data['balances'][0]['remaining_days']), Decimal('18.0'))


# ---------------------------------------------------------------------------
# Group 4: hr_payroll_summary (5 tests)
# ---------------------------------------------------------------------------

class HRPayrollSummaryTests(ReportsPhase10TestCase):

    def setUp(self):
        super().setUp()
        self.url = '/api/reports/hr/payroll/'

    def test_admin_can_access(self):
        self._auth(self.admin)
        resp = self.client.get(self.url + '?date_from=2026-05-01&date_to=2026-05-31')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_cashier_forbidden(self):
        self._auth(self.cashier)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_response_structure(self):
        self._auth(self.admin)
        resp = self.client.get(self.url + '?date_from=2026-05-01&date_to=2026-05-31')
        for key in ('period_count', 'overall', 'periods', 'by_department'):
            self.assertIn(key, resp.data)

    def test_period_count_correct(self):
        self._auth(self.admin)
        resp = self.client.get(self.url + '?date_from=2026-05-01&date_to=2026-05-31')
        self.assertEqual(resp.data['period_count'], 1)

    def test_overall_totals_correct(self):
        self._auth(self.admin)
        resp = self.client.get(self.url + '?date_from=2026-05-01&date_to=2026-05-31')
        self.assertEqual(
            Decimal(resp.data['overall']['total_net']),
            Decimal('1600000.00'),
        )


# ---------------------------------------------------------------------------
# Group 5: project_performance (5 tests)
# ---------------------------------------------------------------------------

class ProjectPerformanceTests(ReportsPhase10TestCase):

    def setUp(self):
        super().setUp()
        self.url = '/api/reports/projects/performance/'

    def test_admin_can_access(self):
        self._auth(self.admin)
        resp = self.client.get(self.url + '?date_from=2026-01-01&date_to=2026-12-31')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_cashier_forbidden(self):
        self._auth(self.cashier)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_project_fields_present(self):
        self._auth(self.admin)
        resp = self.client.get(self.url + '?date_from=2026-01-01&date_to=2026-12-31')
        self.assertIn('projects', resp.data)
        if resp.data['projects']:
            proj = resp.data['projects'][0]
            for field in ('id', 'budget', 'actual_cost', 'budget_variance',
                          'budget_utilisation_pct', 'is_over_budget', 'task_counts'):
                self.assertIn(field, proj)

    def test_budget_variance_calculated(self):
        self._auth(self.admin)
        resp = self.client.get(self.url + '?project_id=' + str(self.project.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['project_count'], 1)
        proj = resp.data['projects'][0]
        # budget=10000000, actual=6000000 → variance=4000000
        self.assertEqual(Decimal(proj['budget_variance']), Decimal('4000000.00'))

    def test_task_counts_correct(self):
        """Project has 1 'done' task and 1 'in_progress' task."""
        self._auth(self.admin)
        resp = self.client.get(self.url + '?project_id=' + str(self.project.id))
        tc = resp.data['projects'][0]['task_counts']
        self.assertEqual(tc['done'], 1)
        self.assertEqual(tc['in_progress'], 1)
        self.assertEqual(tc['total'], 2)


# ---------------------------------------------------------------------------
# Group 6: project_time_summary (5 tests)
# ---------------------------------------------------------------------------

class ProjectTimeSummaryTests(ReportsPhase10TestCase):

    def setUp(self):
        super().setUp()
        self.url = '/api/reports/projects/time/'

    def test_admin_can_access(self):
        self._auth(self.admin)
        resp = self.client.get(self.url + '?date_from=2026-05-01&date_to=2026-05-31')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_cashier_forbidden(self):
        self._auth(self.cashier)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_response_structure(self):
        self._auth(self.admin)
        resp = self.client.get(self.url + '?date_from=2026-05-01&date_to=2026-05-31')
        for key in ('total_hours', 'total_entries', 'by_project', 'by_project_and_staff'):
            self.assertIn(key, resp.data)

    def test_total_hours_correct(self):
        self._auth(self.admin)
        resp = self.client.get(
            self.url + f'?date_from=2026-05-01&date_to=2026-05-31&project_id={self.project.id}'
        )
        self.assertEqual(Decimal(resp.data['total_hours']), Decimal('8.00'))

    def test_staff_filter(self):
        self._auth(self.admin)
        resp = self.client.get(
            self.url + f'?date_from=2026-05-01&date_to=2026-05-31&staff_id={self.cashier.id}'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for row in resp.data['by_project_and_staff']:
            self.assertEqual(row['staff_id'], self.cashier.id)


# ---------------------------------------------------------------------------
# Group 7: tax_efris_export (5 tests)
# ---------------------------------------------------------------------------

class TaxEfrisExportTests(ReportsPhase10TestCase):

    def setUp(self):
        super().setUp()
        self.url = '/api/reports/tax/efris-export/'

    def test_admin_can_access_json(self):
        self._auth(self.admin)
        resp = self.client.get(self.url + '?date_from=2026-01-01&date_to=2026-12-31')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('records', resp.data)
        self.assertIn('summary', resp.data)

    def test_accountant_can_access(self):
        self._auth(self.accountant)
        resp = self.client.get(self.url + '?date_from=2026-01-01&date_to=2026-12-31')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_cashier_forbidden(self):
        self._auth(self.cashier)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_fdn_in_accepted_record(self):
        self._auth(self.admin)
        resp = self.client.get(self.url + '?date_from=2026-01-01&date_to=2026-12-31')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        accepted = [r for r in resp.data['records'] if r['fiscal_status'] == 'accepted']
        self.assertTrue(len(accepted) > 0)
        self.assertEqual(accepted[0]['fdn'], 'FDN-2026-001')

    def test_csv_export_returns_correct_content_type(self):
        self._auth(self.admin)
        resp = self.client.get(
            self.url + '?date_from=2026-01-01&date_to=2026-12-31&format=csv'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('text/csv', resp.get('Content-Type', ''))
        self.assertIn('attachment', resp.get('Content-Disposition', ''))


# ---------------------------------------------------------------------------
# Group 8: Enhanced dashboard (5 tests)
# ---------------------------------------------------------------------------

class EnhancedDashboardTests(ReportsPhase10TestCase):

    def setUp(self):
        super().setUp()
        self.url = '/api/reports/dashboard/'

    def test_admin_dashboard_has_hr_section(self):
        self._auth(self.admin)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('active_employees', resp.data)
        self.assertIn('latest_payroll', resp.data)
        self.assertEqual(resp.data['role'], 'admin')

    def test_manager_dashboard_has_top_products(self):
        self._auth(self.manager)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('top_products_today', resp.data)
        self.assertEqual(resp.data['role'], 'manager')

    def test_accountant_dashboard_has_efris_count(self):
        self._auth(self.accountant)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('pending_efris_submissions', resp.data)
        self.assertIn('today_tax_collected', resp.data)
        self.assertEqual(resp.data['role'], 'accountant')

    def test_cashier_no_open_shift_returns_zeros(self):
        self._auth(self.cashier)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['today_sales'], 0)

    def test_unauthenticated_rejected(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
```

Run all tests with:

```bash
docker compose exec backend python manage.py test reports.tests_phase10
```

---

## Quality Checklist

Work through this list before opening a PR.

### Views
- [ ] All 7 new views use `@api_view(['GET'])` + `@permission_classes([...])` pattern
- [ ] All date-filtered views use `_parse_dates(request)` — no duplicate parsing logic
- [ ] `hr_headcount`, `hr_attendance_summary`, `hr_leave_summary`, `hr_payroll_summary` use `(IsAdminOrManager | IsAccountantOrAbove)` permission — use class-level `|` operator (not instance-level)
- [ ] `project_performance`, `project_time_summary` use `IsAdminOrManager`
- [ ] `tax_efris_export` uses `(IsAdminOrManager | IsAccountantOrAbove)`
- [ ] All HR/project models are imported inside the view function (lazy import) to avoid circular imports
- [ ] `hr_leave_summary` computes `remaining_days` from the Python `@property`, not a DB annotation
- [ ] `hr_attendance_summary` does NOT call `hours_worked` inside a DB queryset — hours computed from Python `duration.total_seconds()`
- [ ] `project_time_summary` references `staff_id` (not `employee_id`) — matches `ProjectTimeEntry.staff_id`
- [ ] `hr_payroll_summary` references `gross_pay` and `net_pay` (not `gross_salary`/`net_salary`) — matches `PaySlip` fields
- [ ] `tax_efris_export` uses `select_related('fiscal_invoice')` on the sale queryset
- [ ] `tax_efris_export` CSV export uses Python `csv.DictWriter`, returns `HttpResponse` with `content_type='text/csv'`
- [ ] `tax_efris_export` sets `Content-Disposition` header with a date-stamped filename
- [ ] Enhanced `dashboard` returns `role` key in all response variants
- [ ] Enhanced `dashboard` lazy-imports `FiscalInvoice`, `Employee`, `PayrollPeriod` to avoid circular imports
- [ ] Permission operator syntax uses class-level `|`: `[(IsAdminOrManager | IsAccountantOrAbove)()]`

### URLs
- [ ] 7 new paths added to `reports/urls.py`
- [ ] No duplicate `dashboard` path — the existing entry serves the enhanced view
- [ ] All URL names are kebab-case: `hr-headcount`, `hr-attendance-summary`, etc.
- [ ] No URL prefix conflicts with existing paths

### Tests
- [ ] 35+ test methods total (5 per group × 8 groups + attendance `setUpTestData` fixtures)
- [ ] All test classes extend `TenantTestCase`
- [ ] All `self.client` instances are `TenantClient`
- [ ] `setUpTestData` creates all shared fixtures
- [ ] Group 1: 5 HR headcount tests
- [ ] Group 2: 5 HR attendance tests
- [ ] Group 3: 5 HR leave summary tests
- [ ] Group 4: 5 HR payroll summary tests
- [ ] Group 5: 5 project performance tests
- [ ] Group 6: 5 project time summary tests
- [ ] Group 7: 5 EFRIS export tests (including CSV content-type check)
- [ ] Group 8: 5 enhanced dashboard tests (admin, manager, accountant, cashier, unauthenticated)
- [ ] `test_remaining_days_computed_correctly` asserts 18.0 (21 + 2 - 5)
- [ ] `test_budget_variance_calculated` asserts 4000000.00
- [ ] `test_task_counts_correct` asserts done=1, in_progress=1, total=2
- [ ] All 40 tests pass: `docker compose exec backend python manage.py test reports.tests_phase10`

### No New Migrations Required
- [ ] No `makemigrations` needed — no new models
- [ ] Verify: `python manage.py makemigrations --check` returns exit code 0

---

## API Reference

### New Endpoints

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/api/reports/hr/headcount/` | AdminOrManager \| AccountantOrAbove | Employee count by dept/status/type |
| GET | `/api/reports/hr/attendance/` | AdminOrManager \| AccountantOrAbove | Hours worked per employee by period |
| GET | `/api/reports/hr/leave/` | AdminOrManager \| AccountantOrAbove | Leave balance and usage per employee |
| GET | `/api/reports/hr/payroll/` | AdminOrManager \| AccountantOrAbove | Payroll period totals and dept breakdown |
| GET | `/api/reports/projects/performance/` | AdminOrManager | Budget/actual/variance per project |
| GET | `/api/reports/projects/time/` | AdminOrManager | Time entries by project and staff |
| GET | `/api/reports/tax/efris-export/` | AdminOrManager \| AccountantOrAbove | EFRIS compliance export (JSON or CSV) |
| GET | `/api/reports/dashboard/` | Authenticated | Role-specific KPI dashboard (existing URL, enhanced) |

### Query Parameters Summary

| Endpoint | Parameters |
|---|---|
| `hr/headcount/` | `date_from`, `date_to`, `department_id`, `employment_status`, `employment_type` |
| `hr/attendance/` | `date_from`, `date_to`, `department_id`, `employee_id` |
| `hr/leave/` | `year`, `employee_id`, `department_id` |
| `hr/payroll/` | `date_from`, `date_to`, `status`, `department_id` |
| `projects/performance/` | `date_from`, `date_to`, `status`, `project_id` |
| `projects/time/` | `date_from`, `date_to`, `project_id`, `staff_id` |
| `tax/efris-export/` | `date_from`, `date_to`, `status`, `outlet`, `format` (json\|csv) |
| `dashboard/` | `outlet` |

### Response Examples

**`GET /api/reports/hr/headcount/?date_from=2026-01-01&date_to=2026-12-31`**

```json
{
  "total": 12,
  "by_department": [
    {"department": 1, "dept_name": "Operations", "count": 7},
    {"department": 2, "dept_name": "Finance", "count": 5}
  ],
  "by_status": [
    {"employment_status": "active", "count": 10},
    {"employment_status": "on_leave", "count": 2}
  ],
  "by_type": [
    {"employment_type": "full_time", "count": 9},
    {"employment_type": "part_time", "count": 3}
  ],
  "date_from": "2026-01-01",
  "date_to": "2026-12-31"
}
```

**`GET /api/reports/projects/performance/?date_from=2026-01-01&date_to=2026-12-31`**

```json
{
  "date_from": "2026-01-01",
  "date_to": "2026-12-31",
  "project_count": 2,
  "summary": {
    "total_budget": "25000000.00",
    "total_actual_cost": "12000000.00",
    "total_variance": "13000000.00"
  },
  "projects": [
    {
      "id": 1,
      "project_number": "PRJ-20260101-0001",
      "name": "Pump Upgrade",
      "status": "active",
      "manager_id": 3,
      "start_date": "2026-01-01",
      "end_date": "2026-06-30",
      "budget": "10000000.00",
      "actual_cost": "6000000.00",
      "budget_variance": "4000000.00",
      "budget_utilisation_pct": "60.00",
      "is_over_budget": false,
      "task_counts": {
        "total": 5,
        "todo": 2,
        "in_progress": 1,
        "blocked": 0,
        "done": 2,
        "cancelled": 0
      }
    }
  ]
}
```

**`GET /api/reports/tax/efris-export/?date_from=2026-05-01&date_to=2026-05-31`**

```json
{
  "date_from": "2026-05-01",
  "date_to": "2026-05-31",
  "summary": {
    "total_sales": 480,
    "total_grand": "28800000.00",
    "total_tax": "4381355.93",
    "accepted_count": 471,
    "pending_count": 3,
    "rejected_count": 2,
    "no_submission_count": 4
  },
  "records": [
    {
      "sale_id": 1,
      "receipt_number": "S001-2026-0001",
      "sale_date": "2026-05-01",
      "sale_time": "09:15:00",
      "outlet_id": 1,
      "grand_total": "59000.00",
      "tax_total": "9000.00",
      "fiscal_status": "accepted",
      "fdn": "FDN-2026-001",
      "invoice_id": "INV-001",
      "verification_code": "VER-001",
      "submitted_at": "2026-05-01T09:15:03+00:00",
      "accepted_at": "2026-05-01T09:15:05+00:00"
    }
  ]
}
```

**`GET /api/reports/dashboard/` — admin role**

```json
{
  "role": "admin",
  "today_sales": 47,
  "today_revenue": "2820000.00",
  "today_tax_collected": "429152.54",
  "active_shifts": 3,
  "low_stock_count": 2,
  "top_products_today": [
    {"product": 12, "product_name": "Petrol", "total_revenue": "1500000.00", "total_qty": "300.000"}
  ],
  "active_employees": 12,
  "latest_payroll": {
    "name": "May 2026",
    "end_date": "2026-05-31",
    "total_gross": "14400000.00",
    "total_net": "11520000.00",
    "status": "paid"
  },
  "date": "2026-05-13"
}
```

---

## Example curl Commands

### 1. HR Headcount — All Active Employees

```bash
TOKEN="<access token>"

curl -s "http://localhost:8000/api/reports/hr/headcount/?date_from=2025-01-01&date_to=2026-12-31&employment_status=active" \
  -H "Authorization: Bearer $TOKEN" | jq .
```

---

### 2. HR Attendance — May 2026

```bash
curl -s "http://localhost:8000/api/reports/hr/attendance/?date_from=2026-05-01&date_to=2026-05-31" \
  -H "Authorization: Bearer $TOKEN" | jq '.total_hours'
```

---

### 3. HR Leave Summary — Current Year

```bash
curl -s "http://localhost:8000/api/reports/hr/leave/?year=2026" \
  -H "Authorization: Bearer $TOKEN" | jq '.balances | length'
```

---

### 4. HR Payroll — Paid Periods This Year

```bash
curl -s "http://localhost:8000/api/reports/hr/payroll/?date_from=2026-01-01&date_to=2026-12-31&status=paid" \
  -H "Authorization: Bearer $TOKEN" | jq '{periods: .period_count, net: .overall.total_net}'
```

---

### 5. Project Performance — Active Projects

```bash
curl -s "http://localhost:8000/api/reports/projects/performance/?date_from=2026-01-01&date_to=2026-12-31&status=active" \
  -H "Authorization: Bearer $TOKEN" | jq '.projects[] | {name, variance: .budget_variance, over: .is_over_budget}'
```

---

### 6. Project Time — Single Project

```bash
curl -s "http://localhost:8000/api/reports/projects/time/?date_from=2026-01-01&date_to=2026-12-31&project_id=1" \
  -H "Authorization: Bearer $TOKEN" | jq '{total_hours, entries: .total_entries}'
```

---

### 7. EFRIS Export — JSON

```bash
curl -s "http://localhost:8000/api/reports/tax/efris-export/?date_from=2026-05-01&date_to=2026-05-31" \
  -H "Authorization: Bearer $TOKEN" | jq '.summary'
```

---

### 8. EFRIS Export — CSV Download

```bash
curl -s "http://localhost:8000/api/reports/tax/efris-export/?date_from=2026-05-01&date_to=2026-05-31&format=csv" \
  -H "Authorization: Bearer $TOKEN" \
  -o efris-may-2026.csv

wc -l efris-may-2026.csv  # Should be: sale_count + 1 (header row)
```

---

### 9. Role-Based Dashboard — Admin

```bash
curl -s "http://localhost:8000/api/reports/dashboard/" \
  -H "Authorization: Bearer $TOKEN" | jq '{role, sales: .today_sales, employees: .active_employees}'
```

---

## Implementation Order

Execute phases in sequence. Each phase has a concrete deliverable before proceeding to the next.

| # | Phase | File(s) to edit | Deliverable | Command to verify |
|---|---|---|---|---|
| 1 | HR headcount view | `reports/views.py` | `hr_headcount` function | `curl GET /api/reports/hr/headcount/` returns 200 |
| 2 | HR attendance view | `reports/views.py` | `hr_attendance_summary` function | `curl GET /api/reports/hr/attendance/` returns 200 |
| 3 | HR leave view | `reports/views.py` | `hr_leave_summary` function | Response has `balances` list |
| 4 | HR payroll view | `reports/views.py` | `hr_payroll_summary` function | Response has `periods` list |
| 5 | Project performance view | `reports/views.py` | `project_performance` function | `task_counts` present in each project |
| 6 | Project time view | `reports/views.py` | `project_time_summary` function | `by_project_and_staff` present |
| 7 | EFRIS export view | `reports/views.py` | `tax_efris_export` function | JSON returns; CSV returns `text/csv` |
| 8 | Enhanced dashboard | `reports/views.py` | Replace `dashboard` function | Admin sees `active_employees`; accountant sees `pending_efris_submissions` |
| 9 | Wire URLs | `reports/urls.py` | 7 new paths added | `manage.py show_urls \| grep reports` lists all 16 paths |
| 10 | Tests | `reports/tests_phase10.py` | 40 passing tests | `manage.py test reports.tests_phase10` |

---

*Last updated: 2026-05-13*  
*Author: Kakebe Technologies backend team*  
*Branch: `feat-phase-10-reports`*
