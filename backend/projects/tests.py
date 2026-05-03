from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from rest_framework import status
from users.models import User
from projects.models import Project, ProjectTask, ProjectExpense, ProjectTimeEntry
from approvals.models import ApprovalPolicy, ApprovalRequest
from system_config.models import SystemConfig

class ProjectTestCase(TenantTestCase):
    def setUp(self):
        # self.tenant is available from TenantTestCase automatically
        self.client = TenantClient(self.tenant)
        self.admin = User.objects.create_user(email='admin@demo.com', username='admin', password='password', role='admin')
        self.manager = User.objects.create_user(email='manager@demo.com', username='manager', password='password', role='manager')
        self.cashier = User.objects.create_user(email='cashier@demo.com', username='cashier', password='password', role='cashier')
        self.client.force_login(self.manager)

    def test_create_project_flow(self):
        # Create
        data = {
            'name': 'Test Project',
            'manager_id': self.manager.id,
            'start_date': '2026-05-01',
            'budget': '10000000'
        }
        res = self.client.post(reverse('project-list'), data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        project = Project.objects.get(pk=res.data['id'])
        self.assertTrue(project.project_number.startswith('PRJ-'))
        self.assertEqual(project.status, Project.Status.DRAFT)

    def test_submit_large_budget_requires_approval(self):
        SystemConfig.objects.create(project_approval_threshold=Decimal('5000000'))
        ApprovalPolicy.objects.create(
            name='High Budget Policy', 
            resource_type='project', 
            approval_levels=[{'level': 1, 'role': 'admin', 'min_approvers': 1, 'description': 'Admin'}]
        )
        project = Project.objects.create(
            project_number='PRJ-TEST', name='Big Project', 
            manager_id=self.manager.id, start_date='2026-05-01', budget=Decimal('10000000')
        )
        res = self.client.post(reverse('project-submit', kwargs={'pk': project.id}))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        project.refresh_from_db()
        self.assertEqual(project.status, Project.Status.PENDING_APPROVAL)
        self.assertIsNotNone(project.approval_request)

    def test_expense_updates_actual_cost(self):
        project = Project.objects.create(
            project_number='PRJ-EXP', name='Expense Test', 
            manager_id=self.manager.id, start_date='2026-05-01', budget=Decimal('1000000')
        )
        data = {
            'project': project.id,
            'description': 'Materials',
            'category': 'materials',
            'amount': '500000',
            'expense_date': '2026-05-02'
        }
        res = self.client.post(reverse('projectexpense-list'), data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        project.refresh_from_db()
        self.assertEqual(project.actual_cost, Decimal('500000'))

    def test_time_entry_logs_hours(self):
        project = Project.objects.create(
            project_number='PRJ-TIME', name='Time Test', 
            manager_id=self.manager.id, start_date='2026-05-01', budget=Decimal('1000000')
        )
        data = {
            'project': project.id,
            'date': '2026-05-02',
            'hours': '2.00',
            'description': 'Work'
        }
        res = self.client.post(reverse('projecttimeentry-list'), data)
        if res.status_code != status.HTTP_201_CREATED:
            print(res.data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ProjectTimeEntry.objects.count(), 1)
        self.assertEqual(ProjectTimeEntry.objects.first().staff_id, self.manager.id)
