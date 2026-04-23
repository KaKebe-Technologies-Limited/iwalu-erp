from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from .models import Client, Domain, TenantEmailVerification

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


@override_settings(
    TENANT_BASE_DOMAIN='localhost',
    TENANT_SELF_REGISTRATION_ENABLED=True,
    CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}},
)
class TenantRegistrationIntegrationTests(TransactionTestCase):
    """
    End-to-end integration tests that actually create a PostgreSQL schema and
    run all tenant migrations. Uses ``TransactionTestCase`` because dropping
    tenant schemas (DDL) cannot happen inside the outer ``TestCase``
    transaction — it would raise 'pending trigger events'.

    These tests are slow (each one runs the full TENANT_APPS migration suite),
    so keep the count small and rely on ``TenantRegistrationValidationTests``
    above for the fast validation coverage.
    """

    def setUp(self):
        self.client = APIClient()
        self.url = '/api/tenants/register/'
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
        self.assertEqual(data['domain'], 'acmefuels.localhost')
        self.assertEqual(data['admin_user']['email'], 'owner@acmefuels.com')
        self.assertEqual(data['admin_user']['role'], 'admin')
        # Admin is created INACTIVE; activation is out-of-band (email).
        self.assertFalse(data['admin_user']['is_active'])
        # JWT tokens are NO LONGER issued at registration — caller must
        # complete email verification first.
        self.assertNotIn('access', data)
        self.assertNotIn('refresh', data)
        self.assertIn('message', data)

        # Verify DB state
        self.assertTrue(Client.objects.filter(schema_name='acmefuels').exists())
        self.assertTrue(Domain.objects.filter(domain='acmefuels.localhost').exists())
        admin = User.objects.get(email='owner@acmefuels.com')
        self.assertEqual(admin.role, 'admin')
        self.assertFalse(admin.is_active)
        self.assertFalse(admin.is_staff)
        self.assertFalse(admin.is_superuser)
        self.assertTrue(admin.check_password('securepass123'))


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
        self.assertIn('disabled', response.json()['error'].lower())


@override_settings(TENANT_BASE_DOMAIN='localhost')
class EmailVerificationTests(TestCase):
    """
    Tests for GET /api/tenants/verify-email/.
    Uses a pre-created Client + User + TenantEmailVerification to avoid
    the slow schema-creation path.
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
        self.assertIn('refresh', data)
        self.assertIn('redirect_url', data)
        self.assertIn('verifyco', data['redirect_url'])
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.verification.refresh_from_db()
        self.assertIsNotNone(self.verification.used_at)

    def test_missing_token_returns_400(self):
        response = self.api.get('/api/tenants/verify-email/')
        self.assertEqual(response.status_code, 400)

    def test_invalid_token_returns_400(self):
        response = self.api.get(self._verify_url('00000000-0000-0000-0000-000000000000'))
        self.assertEqual(response.status_code, 400)

    def test_expired_token_returns_400(self):
        self.verification.expires_at = timezone.now() - timedelta(hours=1)
        self.verification.save()
        response = self.api.get(self._verify_url(self.verification.token))
        self.assertEqual(response.status_code, 400)
        self.assertIn('expired', response.json()['error'].lower())

    def test_already_used_token_returns_400(self):
        self.verification.used_at = timezone.now()
        self.verification.save()
        response = self.api.get(self._verify_url(self.verification.token))
        self.assertEqual(response.status_code, 400)
        self.assertIn('already been used', response.json()['error'].lower())
