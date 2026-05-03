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
        self.client = TenantClient(self.tenant)
        self.admin = User.objects.create_user(email='admin@demo.com', username='admin', password='password', role='admin')
        self.manager = User.objects.create_user(email='manager@demo.com', username='manager', password='password', role='manager')
        self.cashier = User.objects.create_user(email='cashier@demo.com', username='cashier', password='password', role='cashier')

    def _auth(self, user):
        response = self.client.post('/api/auth/login/', {
            'email': user.email, 'password': 'password',
        })
        token = response.json()['access']
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {token}'

    def test_create_project_flow(self):
        self._auth(self.manager)
        data = {
            'name': 'Test Project',
            'manager_id': self.manager.id,
            'start_date': '2026-05-01',
            'budget': '10000000'
        }
        res = self.client.post(reverse('project-list'), data, content_type='application/json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        project = Project.objects.get(pk=res.data['id'])
        self.assertTrue(project.project_number.startswith('PRJ-'))
        self.assertEqual(project.status, Project.Status.DRAFT)

    def test_create_project_as_cashier_forbidden(self):
        self._auth(self.cashier)
        data = {
            'name': 'Cashier Project',
            'manager_id': self.cashier.id,
            'start_date': '2026-05-01',
            'budget': '1000000'
        }
        res = self.client.post(reverse('project-list'), data, content_type='application/json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_submit_large_budget_requires_approval(self):
        self._auth(self.manager)
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

    def test_submit_below_threshold_auto_activates(self):
        self._auth(self.manager)
        SystemConfig.objects.create(project_approval_threshold=Decimal('50000000'))
        project = Project.objects.create(
            project_number='PRJ-SMALL', name='Small Project',
            manager_id=self.manager.id, start_date='2026-05-01', budget=Decimal('1000000')
        )
        res = self.client.post(reverse('project-submit', kwargs={'pk': project.id}))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        project.refresh_from_db()
        self.assertEqual(project.status, Project.Status.ACTIVE)

    def test_expense_updates_actual_cost(self):
        self._auth(self.manager)
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
        res = self.client.post(reverse('projectexpense-list'), data, content_type='application/json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        project.refresh_from_db()
        self.assertEqual(project.actual_cost, Decimal('500000'))

    def test_expense_update_adjusts_actual_cost(self):
        self._auth(self.manager)
        project = Project.objects.create(
            project_number='PRJ-UPD', name='Update Test',
            manager_id=self.manager.id, start_date='2026-05-01', budget=Decimal('1000000')
        )
        res = self.client.post(reverse('projectexpense-list'), {
            'project': project.id, 'description': 'Materials',
            'category': 'materials', 'amount': '500000', 'expense_date': '2026-05-02'
        }, content_type='application/json')
        expense_id = res.data['id']

        res = self.client.patch(
            reverse('projectexpense-detail', kwargs={'pk': expense_id}),
            {'amount': '300000'},
            content_type='application/json'
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        project.refresh_from_db()
        self.assertEqual(project.actual_cost, Decimal('300000'))

    def test_expense_delete_reduces_actual_cost(self):
        self._auth(self.manager)
        project = Project.objects.create(
            project_number='PRJ-DEL', name='Delete Test',
            manager_id=self.manager.id, start_date='2026-05-01', budget=Decimal('1000000')
        )
        res = self.client.post(reverse('projectexpense-list'), {
            'project': project.id, 'description': 'Materials',
            'category': 'materials', 'amount': '500000', 'expense_date': '2026-05-02'
        }, content_type='application/json')
        expense_id = res.data['id']

        res = self.client.delete(reverse('projectexpense-detail', kwargs={'pk': expense_id}))
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        project.refresh_from_db()
        self.assertEqual(project.actual_cost, Decimal('0'))

    def test_time_entry_logs_hours(self):
        self._auth(self.manager)
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
        res = self.client.post(reverse('projecttimeentry-list'), data, content_type='application/json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ProjectTimeEntry.objects.count(), 1)
        self.assertEqual(ProjectTimeEntry.objects.first().staff_id, self.manager.id)

    def test_end_date_before_start_date_rejected(self):
        self._auth(self.manager)
        data = {
            'name': 'Bad Dates',
            'manager_id': self.manager.id,
            'start_date': '2026-06-01',
            'end_date': '2026-05-01',
            'budget': '1000000'
        }
        res = self.client.post(reverse('project-list'), data, content_type='application/json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_project_lifecycle_actions(self):
        self._auth(self.manager)
        project = Project.objects.create(
            project_number='PRJ-LIFE', name='Lifecycle Test',
            manager_id=self.manager.id, start_date='2026-05-01',
            budget=Decimal('1000000'), status=Project.Status.ACTIVE
        )
        res = self.client.post(reverse('project-hold', kwargs={'pk': project.id}))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        project.refresh_from_db()
        self.assertEqual(project.status, Project.Status.ON_HOLD)

        res = self.client.post(reverse('project-resume', kwargs={'pk': project.id}))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        project.refresh_from_db()
        self.assertEqual(project.status, Project.Status.ACTIVE)

        res = self.client.post(reverse('project-complete', kwargs={'pk': project.id}))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        project.refresh_from_db()
        self.assertEqual(project.status, Project.Status.COMPLETED)
