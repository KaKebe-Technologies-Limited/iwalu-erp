from decimal import Decimal
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from django.contrib.auth import get_user_model

from outlets.models import Outlet
from .models import Department, Employee, LeaveType, LeaveBalance, PayrollPeriod
from . import services

User = get_user_model()


class HRTestBase(TenantTestCase):
    def setUp(self):
        self.client = TenantClient(self.tenant)
        self.admin = User.objects.create_user(
            email='admin@test.com', username='admin',
            password='testpass123', role='admin',
        )
        self.manager = User.objects.create_user(
            email='manager@test.com', username='manager',
            password='testpass123', role='manager',
        )
        self.cashier = User.objects.create_user(
            email='cashier@test.com', username='cashier',
            password='testpass123', role='cashier',
        )
        self.outlet = Outlet.objects.create(
            name='Main Station', outlet_type='fuel_station',
        )
        self.dept = Department.objects.create(
            name='Operations', outlet=self.outlet,
        )

        # Seed finance accounts for payroll tests
        from finance.models import Account
        from finance.management.commands.seed_chart_of_accounts import DEFAULT_ACCOUNTS
        for code, name, account_type in DEFAULT_ACCOUNTS:
            Account.objects.get_or_create(
                code=code,
                defaults={'name': name, 'account_type': account_type, 'is_system': True},
            )

    def _auth(self, user):
        response = self.client.post('/api/auth/login/', {
            'email': user.email, 'password': 'testpass123',
        })
        token = response.json()['access']
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {token}'

    def _create_employee(self, user, salary=Decimal('800000')):
        return Employee.objects.create(
            user_id=user.pk,
            employee_number=services.generate_employee_number(),
            department=self.dept,
            outlet=self.outlet,
            designation='Staff',
            date_hired=timezone.now().date(),
            basic_salary=salary,
        )


class DepartmentAPITest(HRTestBase):
    def test_list_departments(self):
        self._auth(self.admin)
        response = self.client.get('/api/departments/')
        self.assertEqual(response.status_code, 200)

    def test_create_department(self):
        self._auth(self.admin)
        response = self.client.post('/api/departments/', {
            'name': 'Finance',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)

    def test_cashier_cannot_create_department(self):
        self._auth(self.cashier)
        response = self.client.post('/api/departments/', {
            'name': 'HR',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 403)


class EmployeeAPITest(HRTestBase):
    def test_create_employee(self):
        self._auth(self.admin)
        response = self.client.post('/api/employees/', {
            'user_id': self.cashier.pk,
            'department': self.dept.pk,
            'outlet': self.outlet.pk,
            'designation': 'Cashier',
            'date_hired': '2026-01-15',
            'basic_salary': '800000',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()['employee_number'].startswith('EMP-'))

    def test_terminate_employee(self):
        self._auth(self.admin)
        emp = self._create_employee(self.cashier)
        response = self.client.post(f'/api/employees/{emp.pk}/terminate/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['employment_status'], 'terminated')


class LeaveTest(HRTestBase):
    def test_submit_and_approve_leave(self):
        emp = self._create_employee(self.cashier)
        leave_type = LeaveType.objects.create(
            name='Annual Leave', days_per_year=21, is_paid=True,
        )
        LeaveBalance.objects.create(
            employee=emp, leave_type=leave_type,
            year=timezone.now().year, entitled_days=21,
        )

        # Submit
        self._auth(self.cashier)
        response = self.client.post('/api/leave-requests/', {
            'leave_type': leave_type.pk,
            'start_date': '2026-04-01',
            'end_date': '2026-04-05',
            'days_requested': '5',
            'reason': 'Family visit',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        request_id = response.json()['id']

        # Approve
        self._auth(self.admin)
        response = self.client.post(f'/api/leave-requests/{request_id}/approve/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'approved')

        # Check balance deducted
        balance = LeaveBalance.objects.get(employee=emp, leave_type=leave_type)
        self.assertEqual(balance.used_days, Decimal('5'))


class AttendanceTest(HRTestBase):
    def test_clock_in_and_out(self):
        self._create_employee(self.cashier)
        self._auth(self.cashier)

        # Clock in
        response = self.client.post('/api/attendance/clock-in/', {
            'outlet_id': self.outlet.pk,
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)

        # Clock out
        response = self.client.post('/api/attendance/clock-out/')
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json()['clock_out'])

    def test_cannot_clock_in_twice(self):
        self._create_employee(self.cashier)
        self._auth(self.cashier)
        self.client.post('/api/attendance/clock-in/', {}, content_type='application/json')
        response = self.client.post('/api/attendance/clock-in/', {}, content_type='application/json')
        self.assertEqual(response.status_code, 400)


class PayrollTest(HRTestBase):
    def test_paye_calculation(self):
        # Below first bracket
        self.assertEqual(services.calculate_paye(Decimal('200000')), Decimal('0'))
        # In second bracket: 10% of (300000-235000) = 6500
        self.assertEqual(services.calculate_paye(Decimal('300000')), Decimal('6500'))
        # In third bracket
        tax = services.calculate_paye(Decimal('400000'))
        expected = Decimal('10000') + Decimal('13000')  # 10% of 100k + 20% of 65k
        self.assertEqual(tax, expected)

    def test_nssf_calculation(self):
        employee, employer = services.calculate_nssf(Decimal('800000'))
        self.assertEqual(employee, Decimal('40000'))
        self.assertEqual(employer, Decimal('80000'))

    def test_process_and_approve_payroll(self):
        self._create_employee(self.cashier, salary=Decimal('800000'))
        period = PayrollPeriod.objects.create(
            name='March 2026',
            start_date='2026-03-01',
            end_date='2026-03-31',
        )

        # Process
        self._auth(self.admin)
        response = self.client.post(f'/api/payroll-periods/{period.pk}/process/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'processing')
        self.assertEqual(data['pay_slips_count'], 1)
        self.assertGreater(Decimal(data['total_net']), 0)

        # Approve (creates journal entry)
        response = self.client.post(f'/api/payroll-periods/{period.pk}/approve/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'approved')
        self.assertIsNotNone(data['journal_entry'])
