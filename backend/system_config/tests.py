from decimal import Decimal
from django.core.cache import cache
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from django.contrib.auth import get_user_model

from .models import SystemConfig, ApprovalThreshold, AuditSetting
from . import services

User = get_user_model()


class SystemConfigTestBase(TenantTestCase):
    def setUp(self):
        self.client = TenantClient(self.tenant)
        cache.clear()
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

    def _auth(self, user):
        response = self.client.post('/api/auth/login/', {
            'email': user.email, 'password': 'testpass123',
        })
        token = response.json()['access']
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {token}'


class SystemConfigServiceTests(SystemConfigTestBase):

    def test_get_creates_default(self):
        config = services.get_system_config()
        self.assertIsNotNone(config)
        self.assertEqual(config.currency_code, 'UGX')
        self.assertEqual(config.variance_tolerance_pct, Decimal('0.50'))

    def test_update_config(self):
        config = services.update_system_config({
            'business_name': 'Kakebe Fuels',
            'currency_code': 'UGX',
            'variance_tolerance_pct': Decimal('1.00'),
        })
        self.assertEqual(config.business_name, 'Kakebe Fuels')
        self.assertEqual(config.variance_tolerance_pct, Decimal('1.00'))

    def test_update_invalidates_cache(self):
        services.get_system_config()
        services.update_system_config({'business_name': 'Updated'})
        config = services.get_system_config()
        self.assertEqual(config.business_name, 'Updated')

    def test_singleton_enforcement(self):
        services.get_system_config()
        # Creating another should overwrite (pk forced to 1)
        config = SystemConfig(business_name='Duplicate')
        config.save()
        self.assertEqual(SystemConfig.objects.count(), 1)
        self.assertEqual(SystemConfig.objects.first().business_name, 'Duplicate')


class ApprovalServiceTests(SystemConfigTestBase):

    def test_no_threshold_returns_none(self):
        role = services.get_required_approval_role('purchase_order', Decimal('100'))
        self.assertIsNone(role)

    def test_threshold_match(self):
        ApprovalThreshold.objects.create(
            transaction_type='purchase_order',
            min_amount=Decimal('1000000'),
            requires_role='manager',
        )
        role = services.get_required_approval_role('purchase_order', Decimal('2000000'))
        self.assertEqual(role, 'manager')

    def test_threshold_below_min(self):
        ApprovalThreshold.objects.create(
            transaction_type='purchase_order',
            min_amount=Decimal('1000000'),
            requires_role='manager',
        )
        role = services.get_required_approval_role('purchase_order', Decimal('500000'))
        self.assertIsNone(role)

    def test_threshold_with_max(self):
        ApprovalThreshold.objects.create(
            transaction_type='expense',
            min_amount=Decimal('100000'),
            max_amount=Decimal('500000'),
            requires_role='manager',
        )
        ApprovalThreshold.objects.create(
            transaction_type='expense',
            min_amount=Decimal('500001'),
            requires_role='admin',
        )
        self.assertEqual(
            services.get_required_approval_role('expense', Decimal('300000')),
            'manager',
        )
        self.assertEqual(
            services.get_required_approval_role('expense', Decimal('1000000')),
            'admin',
        )

    def test_check_approval_admin(self):
        ApprovalThreshold.objects.create(
            transaction_type='purchase_order',
            min_amount=Decimal('1000000'),
            requires_role='admin',
        )
        approved, role = services.check_approval('purchase_order', Decimal('2000000'), 'admin')
        self.assertTrue(approved)

    def test_check_approval_insufficient_role(self):
        ApprovalThreshold.objects.create(
            transaction_type='purchase_order',
            min_amount=Decimal('1000000'),
            requires_role='admin',
        )
        approved, role = services.check_approval('purchase_order', Decimal('2000000'), 'manager')
        self.assertFalse(approved)
        self.assertEqual(role, 'admin')


class SystemConfigAPITests(SystemConfigTestBase):

    def test_get_config(self):
        self._auth(self.cashier)
        response = self.client.get('/api/system-config/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['currency_code'], 'UGX')

    def test_update_config_admin(self):
        services.get_system_config()  # ensure singleton exists
        self._auth(self.admin)
        response = self.client.patch(
            '/api/system-config/1/',
            data={'business_name': 'Kakebe Fuels', 'variance_tolerance_pct': '1.50'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['business_name'], 'Kakebe Fuels')

    def test_update_config_cashier_denied(self):
        self._auth(self.cashier)
        response = self.client.patch(
            '/api/system-config/1/',
            data={'business_name': 'Hacked'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_check_approval_endpoint(self):
        ApprovalThreshold.objects.create(
            transaction_type='purchase_order',
            min_amount=Decimal('1000000'),
            requires_role='manager',
        )
        self._auth(self.manager)
        response = self.client.post(
            '/api/system-config/check-approval/',
            data={'transaction_type': 'purchase_order', 'amount': '2000000'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['approved'])


class ApprovalThresholdAPITests(SystemConfigTestBase):

    def test_create_threshold_admin(self):
        self._auth(self.admin)
        response = self.client.post('/api/approval-thresholds/', {
            'transaction_type': 'purchase_order',
            'min_amount': '1000000',
            'requires_role': 'manager',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)

    def test_create_threshold_cashier_denied(self):
        self._auth(self.cashier)
        response = self.client.post('/api/approval-thresholds/', {
            'transaction_type': 'purchase_order',
            'min_amount': '1000000',
            'requires_role': 'manager',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_validation_min_max(self):
        self._auth(self.admin)
        response = self.client.post('/api/approval-thresholds/', {
            'transaction_type': 'expense',
            'min_amount': '500000',
            'max_amount': '100000',
            'requires_role': 'manager',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_list_thresholds(self):
        ApprovalThreshold.objects.create(
            transaction_type='purchase_order',
            min_amount=Decimal('1000000'),
            requires_role='manager',
        )
        self._auth(self.cashier)
        response = self.client.get('/api/approval-thresholds/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)


class AuditSettingAPITests(SystemConfigTestBase):

    def test_create_audit_setting_admin(self):
        self._auth(self.admin)
        response = self.client.post('/api/audit-settings/', {
            'log_type': 'login',
            'is_enabled': True,
            'retention_days': 90,
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)

    def test_create_audit_setting_cashier_denied(self):
        self._auth(self.cashier)
        response = self.client.post('/api/audit-settings/', {
            'log_type': 'login',
            'is_enabled': True,
            'retention_days': 90,
        }, content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_list_audit_settings_admin(self):
        AuditSetting.objects.create(log_type='login', is_enabled=True)
        self._auth(self.admin)
        response = self.client.get('/api/audit-settings/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)

    def test_list_audit_settings_cashier_denied(self):
        self._auth(self.cashier)
        response = self.client.get('/api/audit-settings/')
        self.assertEqual(response.status_code, 403)
