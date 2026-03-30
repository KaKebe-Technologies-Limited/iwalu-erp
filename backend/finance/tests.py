from decimal import Decimal
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from django.contrib.auth import get_user_model

from outlets.models import Outlet
from .models import Account, FiscalPeriod, JournalEntry, JournalEntryLine
from . import services

User = get_user_model()


class FinanceTestBase(TenantTestCase):
    def setUp(self):
        self.client = TenantClient(self.tenant)
        self.admin = User.objects.create_user(
            email='admin@test.com', username='admin',
            password='testpass123', role='admin',
        )
        self.accountant = User.objects.create_user(
            email='acct@test.com', username='accountant',
            password='testpass123', role='accountant',
        )
        self.cashier = User.objects.create_user(
            email='cashier@test.com', username='cashier',
            password='testpass123', role='cashier',
        )
        self.outlet = Outlet.objects.create(
            name='Main Station', outlet_type='fuel_station',
        )
        # Seed system accounts
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


class AccountAPITest(FinanceTestBase):
    def test_list_accounts(self):
        self._auth(self.admin)
        response = self.client.get('/api/accounts/')
        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.json()['count'], 0)

    def test_create_account(self):
        self._auth(self.accountant)
        response = self.client.post('/api/accounts/', {
            'code': '6000', 'name': 'Marketing Expense',
            'account_type': 'expense',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)

    def test_cashier_cannot_create_account(self):
        self._auth(self.cashier)
        response = self.client.post('/api/accounts/', {
            'code': '6001', 'name': 'Test',
            'account_type': 'expense',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_cannot_delete_system_account(self):
        self._auth(self.admin)
        acct = Account.objects.get(code='1000')
        response = self.client.delete(f'/api/accounts/{acct.pk}/')
        self.assertEqual(response.status_code, 400)

    def test_filter_by_type(self):
        self._auth(self.admin)
        response = self.client.get('/api/accounts/?account_type=asset')
        self.assertEqual(response.status_code, 200)
        for item in response.json()['results']:
            self.assertEqual(item['account_type'], 'asset')


class JournalEntryServiceTest(FinanceTestBase):
    def test_create_balanced_entry(self):
        cash = Account.objects.get(code='1000')
        revenue = Account.objects.get(code='4000')
        entry = services.create_journal_entry(
            date=timezone.now().date(),
            description='Test sale',
            lines_data=[
                {'account_id': cash.pk, 'debit': Decimal('10000'), 'credit': Decimal('0')},
                {'account_id': revenue.pk, 'debit': Decimal('0'), 'credit': Decimal('10000')},
            ],
            created_by=self.admin.pk,
        )
        self.assertEqual(entry.status, 'draft')
        self.assertEqual(entry.lines.count(), 2)

    def test_reject_unbalanced_entry(self):
        cash = Account.objects.get(code='1000')
        from rest_framework.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            services.create_journal_entry(
                date=timezone.now().date(),
                description='Bad entry',
                lines_data=[
                    {'account_id': cash.pk, 'debit': Decimal('10000'), 'credit': Decimal('0')},
                ],
                created_by=self.admin.pk,
            )

    def test_post_entry(self):
        cash = Account.objects.get(code='1000')
        revenue = Account.objects.get(code='4000')
        entry = services.create_journal_entry(
            date=timezone.now().date(),
            description='Test',
            lines_data=[
                {'account_id': cash.pk, 'debit': Decimal('5000'), 'credit': Decimal('0')},
                {'account_id': revenue.pk, 'debit': Decimal('0'), 'credit': Decimal('5000')},
            ],
            created_by=self.admin.pk,
        )
        services.post_journal_entry(entry, self.admin.pk)
        entry.refresh_from_db()
        self.assertEqual(entry.status, 'posted')

    def test_void_creates_reversal(self):
        cash = Account.objects.get(code='1000')
        revenue = Account.objects.get(code='4000')
        entry = services.create_journal_entry(
            date=timezone.now().date(),
            description='To void',
            lines_data=[
                {'account_id': cash.pk, 'debit': Decimal('5000'), 'credit': Decimal('0')},
                {'account_id': revenue.pk, 'debit': Decimal('0'), 'credit': Decimal('5000')},
            ],
            created_by=self.admin.pk,
            auto_post=True,
        )
        reversal = services.void_journal_entry(entry, self.admin.pk)
        entry.refresh_from_db()
        self.assertEqual(entry.status, 'voided')
        self.assertEqual(reversal.status, 'posted')

    def test_account_balance(self):
        cash = Account.objects.get(code='1000')
        revenue = Account.objects.get(code='4000')
        services.create_journal_entry(
            date=timezone.now().date(),
            description='Balance test',
            lines_data=[
                {'account_id': cash.pk, 'debit': Decimal('20000'), 'credit': Decimal('0')},
                {'account_id': revenue.pk, 'debit': Decimal('0'), 'credit': Decimal('20000')},
            ],
            created_by=self.admin.pk,
            auto_post=True,
        )
        cash_balance = services.get_account_balance(cash)
        self.assertEqual(cash_balance, Decimal('20000'))
        revenue_balance = services.get_account_balance(revenue)
        self.assertEqual(revenue_balance, Decimal('20000'))


class JournalEntryAPITest(FinanceTestBase):
    def test_create_entry_via_api(self):
        self._auth(self.accountant)
        cash = Account.objects.get(code='1000')
        revenue = Account.objects.get(code='4000')
        response = self.client.post('/api/journal-entries/', {
            'date': timezone.now().date().isoformat(),
            'description': 'API test entry',
            'lines': [
                {'account_id': cash.pk, 'debit': '15000', 'credit': '0'},
                {'account_id': revenue.pk, 'debit': '0', 'credit': '15000'},
            ],
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['status'], 'draft')

    def test_post_entry_via_api(self):
        self._auth(self.admin)
        cash = Account.objects.get(code='1000')
        revenue = Account.objects.get(code='4000')
        entry = services.create_journal_entry(
            date=timezone.now().date(),
            description='Post test',
            lines_data=[
                {'account_id': cash.pk, 'debit': Decimal('5000'), 'credit': Decimal('0')},
                {'account_id': revenue.pk, 'debit': Decimal('0'), 'credit': Decimal('5000')},
            ],
            created_by=self.admin.pk,
        )
        response = self.client.post(f'/api/journal-entries/{entry.pk}/post/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'posted')


class FinancialReportsTest(FinanceTestBase):
    def test_trial_balance(self):
        self._auth(self.admin)
        cash = Account.objects.get(code='1000')
        revenue = Account.objects.get(code='4000')
        services.create_journal_entry(
            date=timezone.now().date(),
            description='Trial balance test',
            lines_data=[
                {'account_id': cash.pk, 'debit': Decimal('50000'), 'credit': Decimal('0')},
                {'account_id': revenue.pk, 'debit': Decimal('0'), 'credit': Decimal('50000')},
            ],
            created_by=self.admin.pk,
            auto_post=True,
        )
        response = self.client.get('/api/finance/trial-balance/')
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_profit_loss(self):
        self._auth(self.admin)
        today = timezone.now().date()
        response = self.client.get(
            f'/api/finance/profit-loss/?date_from={today}&date_to={today}'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('net_income', response.json())

    def test_balance_sheet(self):
        self._auth(self.admin)
        response = self.client.get('/api/finance/balance-sheet/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('total_assets', response.json())
