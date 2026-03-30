from django.db import transaction
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.permissions import IsAdminOrManager, IsAccountantOrAbove
from .models import (
    Department, Employee, LeaveType, LeaveBalance,
    LeaveRequest, Attendance, PayrollPeriod, PaySlip,
)
from .serializers import (
    DepartmentSerializer,
    EmployeeSerializer, EmployeeCreateSerializer,
    LeaveTypeSerializer, LeaveBalanceSerializer,
    LeaveRequestSerializer, LeaveRequestCreateSerializer,
    AttendanceSerializer,
    PayrollPeriodSerializer, PayrollPeriodDetailSerializer,
    PaySlipSerializer,
)
from . import services


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.select_related('outlet').all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminOrManager()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == 'true')
        outlet = self.request.query_params.get('outlet')
        if outlet:
            qs = qs.filter(outlet_id=outlet)
        return qs


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.select_related('department', 'outlet').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['employee_number', 'designation']
    ordering_fields = ['employee_number', 'date_hired', 'basic_salary']

    def get_serializer_class(self):
        if self.action == 'create':
            return EmployeeCreateSerializer
        return EmployeeSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy', 'terminate'):
            return [IsAdminOrManager()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        dept = self.request.query_params.get('department')
        if dept:
            qs = qs.filter(department_id=dept)
        outlet = self.request.query_params.get('outlet')
        if outlet:
            qs = qs.filter(outlet_id=outlet)
        emp_status = self.request.query_params.get('status')
        if emp_status:
            qs = qs.filter(employment_status=emp_status)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            emp_number = services.generate_employee_number()
            employee = serializer.save(employee_number=emp_number)
        return Response(
            EmployeeSerializer(employee).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def terminate(self, request, pk=None):
        from django.utils import timezone
        employee = self.get_object()
        employee.employment_status = 'terminated'
        employee.date_terminated = timezone.now().date()
        employee.save(update_fields=[
            'employment_status', 'date_terminated', 'updated_at',
        ])
        return Response(EmployeeSerializer(employee).data)


class LeaveTypeViewSet(viewsets.ModelViewSet):
    queryset = LeaveType.objects.all()
    serializer_class = LeaveTypeSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminOrManager()]
        return [IsAuthenticated()]


class LeaveBalanceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LeaveBalance.objects.select_related(
        'employee', 'leave_type',
    ).all()
    serializer_class = LeaveBalanceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        employee = self.request.query_params.get('employee')
        if employee:
            qs = qs.filter(employee_id=employee)
        year = self.request.query_params.get('year')
        if year:
            qs = qs.filter(year=year)
        return qs


class LeaveRequestViewSet(viewsets.ModelViewSet):
    queryset = LeaveRequest.objects.select_related(
        'employee', 'leave_type',
    ).all()
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['start_date', 'created_at']

    def get_serializer_class(self):
        if self.action == 'create':
            return LeaveRequestCreateSerializer
        return LeaveRequestSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        employee = self.request.query_params.get('employee')
        if employee:
            qs = qs.filter(employee_id=employee)
        req_status = self.request.query_params.get('status')
        if req_status:
            qs = qs.filter(status=req_status)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Find employee for the current user
        try:
            employee = Employee.objects.get(user_id=request.user.pk)
        except Employee.DoesNotExist:
            return Response(
                {'error': 'No employee record found for current user.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        leave_request = services.submit_leave_request(
            employee=employee,
            leave_type_id=data['leave_type'],
            start_date=data['start_date'],
            end_date=data['end_date'],
            days_requested=data['days_requested'],
            reason=data.get('reason', ''),
        )
        return Response(
            LeaveRequestSerializer(leave_request).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        self.permission_classes = [IsAdminOrManager]
        self.check_permissions(request)
        leave_request = self.get_object()
        services.approve_leave(leave_request, request.user.pk)
        return Response(LeaveRequestSerializer(leave_request).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        self.permission_classes = [IsAdminOrManager]
        self.check_permissions(request)
        leave_request = self.get_object()
        reason = request.data.get('reason', '')
        services.reject_leave(leave_request, request.user.pk, reason)
        return Response(LeaveRequestSerializer(leave_request).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        leave_request = self.get_object()
        # Only the employee who submitted can cancel, and only if pending
        try:
            employee = Employee.objects.get(user_id=request.user.pk)
        except Employee.DoesNotExist:
            return Response(
                {'error': 'No employee record found.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if leave_request.employee_id != employee.pk:
            return Response(
                {'error': 'You can only cancel your own leave requests.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if leave_request.status != 'pending':
            return Response(
                {'error': 'Only pending requests can be cancelled.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        leave_request.status = 'cancelled'
        leave_request.save(update_fields=['status', 'updated_at'])
        return Response(LeaveRequestSerializer(leave_request).data)


class AttendanceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Attendance.objects.select_related('employee').all()
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['date']

    def get_queryset(self):
        qs = super().get_queryset()
        employee = self.request.query_params.get('employee')
        if employee:
            qs = qs.filter(employee_id=employee)
        outlet = self.request.query_params.get('outlet')
        if outlet:
            qs = qs.filter(outlet_id=outlet)
        date_from = self.request.query_params.get('date_from')
        if date_from:
            qs = qs.filter(date__gte=date_from)
        date_to = self.request.query_params.get('date_to')
        if date_to:
            qs = qs.filter(date__lte=date_to)
        return qs

    @action(detail=False, methods=['post'], url_path='clock-in')
    def clock_in(self, request):
        try:
            employee = Employee.objects.get(user_id=request.user.pk)
        except Employee.DoesNotExist:
            return Response(
                {'error': 'No employee record found.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        outlet_id = request.data.get('outlet_id')
        outlet = None
        if outlet_id:
            from outlets.models import Outlet
            outlet = Outlet.objects.get(pk=outlet_id)
        record = services.clock_in(employee, outlet)
        return Response(
            AttendanceSerializer(record).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['post'], url_path='clock-out')
    def clock_out(self, request):
        try:
            employee = Employee.objects.get(user_id=request.user.pk)
        except Employee.DoesNotExist:
            return Response(
                {'error': 'No employee record found.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        record = services.clock_out(employee)
        return Response(AttendanceSerializer(record).data)

    @action(detail=False, methods=['get'], url_path='my-today')
    def my_today(self, request):
        from django.utils import timezone
        try:
            employee = Employee.objects.get(user_id=request.user.pk)
        except Employee.DoesNotExist:
            return Response(
                {'error': 'No employee record found.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        today = timezone.now().date()
        record = Attendance.objects.filter(
            employee=employee, date=today,
        ).first()
        if not record:
            return Response(
                {'detail': 'No attendance record for today.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(AttendanceSerializer(record).data)


class PayrollPeriodViewSet(viewsets.ModelViewSet):
    queryset = PayrollPeriod.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PayrollPeriodDetailSerializer
        return PayrollPeriodSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy',
                           'process', 'approve'):
            return [IsAdminOrManager()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        period = self.get_object()
        services.process_payroll(period, request.user.pk)
        return Response(PayrollPeriodDetailSerializer(period).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        period = self.get_object()
        services.approve_payroll(period, request.user.pk)
        return Response(PayrollPeriodDetailSerializer(period).data)


class PaySlipViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PaySlip.objects.select_related(
        'employee', 'payroll_period',
    ).prefetch_related('lines').all()
    serializer_class = PaySlipSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        employee = self.request.query_params.get('employee')
        if employee:
            qs = qs.filter(employee_id=employee)
        period = self.request.query_params.get('payroll_period')
        if period:
            qs = qs.filter(payroll_period_id=period)
        return qs
