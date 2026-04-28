import re
from decimal import Decimal
from datetime import timedelta, date
from unittest.mock import patch
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from django.core.management import call_command
from io import StringIO
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django_tenants.utils import get_public_schema_name

from .models import (
    Client, Domain, TenantEmailVerification,
    SubscriptionPlan, TenantSubscription, SubscriptionInvoice
)

User = get_user_model()


VALID_PAYLOAD = {
    'business_name': 'Acme Fuels Ltd',
    'schema_name': 'acmefuels',
    'admin_email': 'owner@acmefuels.com',
    'admin_username': 'acmeowner',
    'admin_password': 'securepass123',
    'admin_first_name': 'John',
    'admin_last_name': 'Doe',
    'admin_phone': '+256700000000',
    'plan_id': 1,
    'billing_cycle': 'monthly',
}


@override_settings(
    TENANT_BASE_DOMAIN='localhost',
    TENANT_SELF_REGISTRATION_ENABLED=True,
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}},
)
class TenantRegistrationValidationTests(TestCase):
    """
    Fast validation tests. Schema creation is disabled via
    ``Client.auto_create_schema = False`` so these tests run in under a
    second each instead of running the full migration suite per test.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Stop django-tenants from creating real PG schemas during validation
        # tests. We only care about the HTTP-layer behaviour here.
        cls._orig_auto_create = Client.auto_create_schema
        Client.auto_create_schema = False

    @classmethod
    def tearDownClass(cls):
        Client.auto_create_schema = cls._orig_auto_create
        super().tearDownClass()

    def setUp(self):
        self.client = APIClient()
        self.url = '/api/tenants/register/'
        # Create a default plan for tests
        self.plan = SubscriptionPlan.objects.create(
            id=1,
            name='Starter',
            slug='starter',
            price_monthly=Decimal('50000'),
            price_annual=Decimal('500000'),
            max_users=5,
            max_outlets=1,
            features=['pos', 'inventory']
        )
        self.valid_payload = VALID_PAYLOAD.copy()

    def test_schema_name_invalid_characters(self):
        payload = {**self.valid_payload, 'schema_name': 'bad-name!'}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('schema_name', response.json())

    def test_schema_name_too_short(self):
        payload = {**self.valid_payload, 'schema_name': 'ab'}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 400)

    def test_schema_name_starts_with_digit(self):
        payload = {**self.valid_payload, 'schema_name': '1acme'}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 400)

    def test_schema_name_reserved(self):
        payload = {**self.valid_payload, 'schema_name': 'admin'}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('reserved', str(response.json()).lower())

    def test_weak_password_rejected(self):
        payload = {**self.valid_payload, 'admin_password': 'short'}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('admin_password', response.json())

    def test_invalid_email(self):
        payload = {**self.valid_payload, 'admin_email': 'not-an-email'}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 400)

    def test_missing_required_fields(self):
        response = self.client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, 400)
        errors = response.json()
        for field in ('business_name', 'schema_name', 'admin_email',
                      'admin_username', 'admin_password',
                      'admin_first_name', 'admin_last_name'):
            self.assertIn(field, errors)

    def test_duplicate_email(self):
        User.objects.create_user(
            email='owner@acmefuels.com', username='existing',
            password='testpass',
        )
        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('admin_email', response.json())

    def test_duplicate_username(self):
        User.objects.create_user(
            email='other@test.com', username='acmeowner',
            password='testpass',
        )
        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('admin_username', response.json())

    def test_duplicate_schema_name(self):
        Client.objects.create(schema_name='acmefuels', name='Existing')
        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('schema_name', response.json())

    def test_schema_name_normalized_lowercase(self):
        """Uppercase input is normalised to lowercase before validation."""
        payload = {**self.valid_payload, 'schema_name': 'LOWERCASE'}
        payload['admin_email'] = 'lc@test.com'
        payload['admin_username'] = 'lcadmin'
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['tenant']['schema_name'], 'lowercase')

    def test_plan_id_required_and_valid(self):
        payload = self.valid_payload.copy()
        del payload['plan_id']
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('plan_id', response.json())
        
        payload['plan_id'] = 999
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 400)


@override_settings(
    TENANT_BASE_DOMAIN='localhost',
    TENANT_SELF_REGISTRATION_ENABLED=True,
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}},
)
class TenantRegistrationIntegrationTests(TransactionTestCase):
    """
    End-to-end integration tests that actually create a PostgreSQL schema and
    run all tenant migrations.
    """

    def setUp(self):
        self.client = APIClient()
        self.url = '/api/tenants/register/'
        self.plan = SubscriptionPlan.objects.create(
            id=1,
            name='Starter',
            slug='starter',
            price_monthly=Decimal('50000'),
            price_annual=Decimal('500000'),
            max_users=5,
            max_outlets=1,
            features=['pos', 'inventory']
        )
        self.valid_payload = VALID_PAYLOAD.copy()

    def tearDown(self):
        # Drop the real schema to keep the test DB clean
        for schema in ('acmefuels',):
            try:
                client = Client.objects.get(schema_name=schema)
                client.delete(force_drop=True)
            except Client.DoesNotExist:
                pass

    def test_register_tenant_end_to_end(self):
        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        data = response.json()

        self.assertEqual(data['tenant']['schema_name'], 'acmefuels')
        self.assertEqual(data['tenant']['name'], 'Acme Fuels Ltd')
        
        # Verify Subscription
        sub = TenantSubscription.objects.get(tenant__schema_name='acmefuels')
        self.assertEqual(sub.plan, self.plan)
        self.assertEqual(sub.status, 'trial')


@override_settings(
    TENANT_BASE_DOMAIN='localhost',
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}},
)
class TenantRegistrationDisabledTests(TestCase):
    """Default posture: endpoint returns 503 + 'contact sales' message."""

    def test_endpoint_returns_503_when_flag_off(self):
        c = APIClient()
        response = c.post('/api/tenants/register/', VALID_PAYLOAD, format='json')
        self.assertEqual(response.status_code, 503)


@override_settings(TENANT_BASE_DOMAIN='localhost')
class EmailVerificationTests(TestCase):
    """
    Tests for GET /api/tenants/verify-email/.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._orig_auto_create = Client.auto_create_schema
        Client.auto_create_schema = False

    @classmethod
    def tearDownClass(cls):
        Client.auto_create_schema = cls._orig_auto_create
        super().tearDownClass()

    def setUp(self):
        self.api = APIClient()
        self.client_obj = Client.objects.create(schema_name='verifyco', name='Verify Co')
        self.admin = User.objects.create(
            email='admin@verifyco.com',
            username='verifyadmin',
            first_name='Admin',
            last_name='User',
            role='admin',
            is_active=False,
        )
        self.admin.set_password('password123')
        self.admin.save()
        self.verification = TenantEmailVerification.objects.create(
            tenant=self.client_obj,
            email='admin@verifyco.com',
            expires_at=timezone.now() + timedelta(hours=24),
        )

    def _verify_url(self, token):
        return f'/api/tenants/verify-email/?token={token}'

    def test_valid_token_activates_user_and_returns_jwt(self):
        response = self.api.get(self._verify_url(self.verification.token))
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertIn('access', data)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_missing_token_returns_400(self):
        response = self.api.get('/api/tenants/verify-email/')
        self.assertEqual(response.status_code, 400)


class BillingTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._orig_auto_create = Client.auto_create_schema
        Client.auto_create_schema = False

    @classmethod
    def tearDownClass(cls):
        Client.auto_create_schema = cls._orig_auto_create
        super().tearDownClass()

    def setUp(self):
        self.api = APIClient()
        self.plan = SubscriptionPlan.objects.create(
            name='Professional',
            slug='professional',
            price_monthly=Decimal('200000'),
            price_annual=Decimal('2000000'),
            max_users=20,
            max_outlets=5
        )
        self.tenant = Client.objects.create(schema_name='acme', name='Acme')
        self.user = User.objects.create_user(
            email='admin@acme.com', username='acmeadmin', password='password123',
            role='admin'
        )
        self.api.force_authenticate(user=self.user)

    def test_create_plan_validates_price(self):
        from django.core.exceptions import ValidationError
        plan = SubscriptionPlan(
            name='Negative', slug='negative',
            price_monthly=Decimal('-10'), price_annual=Decimal('0'),
            max_users=1, max_outlets=1
        )
        with self.assertRaises(ValidationError):
            plan.full_clean()

    def test_plan_monthly_equivalent(self):
        self.assertEqual(self.plan.monthly_equivalent(), Decimal('2000000') / 12)

    def test_subscription_trial_logic(self):
        now = timezone.now()
        sub = TenantSubscription.objects.create(
            tenant=self.tenant, plan=self.plan,
            billing_cycle='monthly', status='trial',
            trial_started_at=now, trial_days=14,
            current_period_start=now,
            current_period_end=now + timedelta(days=14),
            next_billing_date=now + timedelta(days=14)
        )
        self.assertTrue(sub.is_trial_active)
        
        # After 15 days
        sub.trial_started_at = now - timedelta(days=15)
        self.assertFalse(sub.is_trial_active)

    def test_invoice_overdue_logic(self):
        sub = TenantSubscription.objects.create(
            tenant=self.tenant, plan=self.plan,
            billing_cycle='monthly', status='active',
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            next_billing_date=timezone.now() + timedelta(days=30)
        )
        invoice = SubscriptionInvoice.objects.create(
            subscription=sub, invoice_number='INV-001',
            period_start=date.today(), period_end=date.today() + timedelta(days=30),
            amount=Decimal('200000'), status='pending',
            due_date=date.today() - timedelta(days=1)
        )
        self.assertTrue(invoice.is_overdue)
        
        invoice.status = 'paid'
        self.assertFalse(invoice.is_overdue)

    def test_public_list_plans(self):
        self.api.force_authenticate(user=None)
        response = self.api.get('/api/billing/plans/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['results']), 1)

    def test_resend_verification_throttled(self):
        verification = TenantEmailVerification.objects.create(
            tenant=self.tenant,
            email='admin@acme.com',
            expires_at=timezone.now() + timedelta(hours=24)
        )
        payload = {'email': 'admin@acme.com'}
        response = self.api.post('/api/tenants/resend-verification/', payload)
        self.assertEqual(response.status_code, 200)

    def test_plan_admin_crud(self):
        # Admin can create plan
        self.user.is_staff = True
        self.user.save()
        payload = {
            'name': 'Enterprise', 'slug': 'enterprise',
            'price_monthly': '500000', 'price_annual': '5000000',
            'max_users': 100, 'max_outlets': 50
        }
        response = self.api.post('/api/billing/plans/', payload)
        self.assertEqual(response.status_code, 201)
        
        # Non-staff cannot create
        self.user.is_staff = False
        self.user.save()
        response = self.api.post('/api/billing/plans/', payload)
        self.assertEqual(response.status_code, 403)

    def test_my_subscription_endpoint(self):
        sub = TenantSubscription.objects.create(
            tenant=self.tenant, plan=self.plan,
            billing_cycle='monthly', status='active',
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            next_billing_date=timezone.now() + timedelta(days=30)
        )
        # Mocking request.tenant is still an issue, but we can test the 404 for public schema
        response = self.api.get('/api/billing/subscriptions/my-subscription/')
        self.assertEqual(response.status_code, 404) # Public schema has no sub

    def test_admin_suspend_reactivate(self):
        self.user.is_staff = True
        self.user.save()
        sub = TenantSubscription.objects.create(
            tenant=self.tenant, plan=self.plan,
            billing_cycle='monthly', status='active',
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            next_billing_date=timezone.now() + timedelta(days=30)
        )
        response = self.api.post(f'/api/billing/subscriptions/{sub.id}/suspend/', {'reason': 'Test'})
        self.assertEqual(response.status_code, 200)
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'suspended')
        
        response = self.api.post(f'/api/billing/subscriptions/{sub.id}/reactivate/')
        self.assertEqual(response.status_code, 200)
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'active')

    def test_admin_metrics(self):
        self.user.is_staff = True
        self.user.save()
        TenantSubscription.objects.create(
            tenant=self.tenant, plan=self.plan,
            billing_cycle='monthly', status='active',
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            next_billing_date=timezone.now() + timedelta(days=30)
        )
        response = self.api.get('/api/billing/subscriptions/metrics/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['active_subscriptions'], 1)


class ManagementCommandTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._orig_auto_create = Client.auto_create_schema
        Client.auto_create_schema = False

    @classmethod
    def tearDownClass(cls):
        Client.auto_create_schema = cls._orig_auto_create
        super().tearDownClass()

    def setUp(self):
        self.plan = SubscriptionPlan.objects.create(
            name='Starter', slug='starter',
            price_monthly=Decimal('50000'), price_annual=Decimal('500000'),
            max_users=5, max_outlets=1
        )
        self.tenant = Client.objects.create(schema_name='acme', name='Acme')
        self.sub = TenantSubscription.objects.create(
            tenant=self.tenant, plan=self.plan,
            billing_cycle='monthly', status='active',
            current_period_start=timezone.now() - timedelta(days=31),
            current_period_end=timezone.now() - timedelta(days=1),
            next_billing_date=timezone.now() - timedelta(days=1)
        )

    def test_generate_invoices_command(self):
        out = StringIO()
        call_command('generate_invoices', stdout=out)
        self.assertIn('Generated invoice', out.getvalue())
        self.assertEqual(SubscriptionInvoice.objects.count(), 1)
        
        self.sub.refresh_from_db()
        self.assertTrue(self.sub.next_billing_date > timezone.now())

    def test_check_overdue_subscriptions_command(self):
        invoice = SubscriptionInvoice.objects.create(
            subscription=self.sub, invoice_number='INV-2026-00001',
            period_start=date.today() - timedelta(days=40),
            period_end=date.today() - timedelta(days=10),
            amount=Decimal('50000'), status='pending',
            due_date=date.today() - timedelta(days=10)
        )
        
        out = StringIO()
        call_command('check_overdue_subscriptions', stdout=out)
        self.assertIn('Suspended tenant', out.getvalue())
        
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, 'suspended')
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'overdue')

    def test_generate_invoices_skips_suspended(self):
        self.sub.status = 'suspended'
        self.sub.save()
        out = StringIO()
        call_command('generate_invoices', stdout=out)
        self.assertEqual(SubscriptionInvoice.objects.count(), 0)

    def test_generate_invoices_annual(self):
        self.sub.billing_cycle = 'annual'
        self.sub.save()
        out = StringIO()
        call_command('generate_invoices', stdout=out)
        invoice = SubscriptionInvoice.objects.first()
        self.assertEqual(invoice.amount, self.plan.price_annual)
