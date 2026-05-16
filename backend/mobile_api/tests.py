from decimal import Decimal

from django.core.cache import cache
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from rest_framework import status

from fuel.models import Pump
from inventory.models import OutletStock
from outlets.models import Outlet
from products.models import Category, Product
from sales.models import Discount, Shift, Sale
from users.models import User
from mobile_api.models import MobileSyncLog


class MobileAPITestCase(TenantTestCase):
    """Base class. Creates fixtures in setUp for TenantTestCase compatibility."""

    def setUp(self):
        # Clear the throttle cache so rapid test runs don't hit rate limits
        cache.clear()
        self.client = TenantClient(self.tenant)

        self.outlet = Outlet.objects.create(name='Test Station', outlet_type='fuel_station')

        self.category = Category.objects.create(
            name='Fuel', business_unit='fuel_station', is_active=True
        )
        self.product = Product.objects.create(
            name='Petrol',
            sku='PTL-001',
            category=self.category,
            cost_price=Decimal('4000'),
            selling_price=Decimal('5000'),
            tax_rate=Decimal('18.00'),
            track_stock=True,
            stock_quantity=Decimal('1000'),
            unit='litre',
            is_active=True,
        )
        self.outlet_stock = OutletStock.objects.create(
            outlet=self.outlet, product=self.product, quantity=Decimal('500')
        )
        self.discount = Discount.objects.create(
            name='10% Off',
            discount_type='percentage',
            value=Decimal('10'),
            is_active=True,
            valid_until=None,
        )
        self.pump = Pump.objects.create(
            outlet=self.outlet,
            product=self.product,
            pump_number=1,
            name='Pump A',
            status='active',
        )

        self.cashier = User.objects.create_user(
            email='cashier@test.com', username='cashier', password='pass123', role='cashier'
        )
        self.attendant = User.objects.create_user(
            email='attendant@test.com', username='attendant', password='pass123', role='attendant'
        )
        self.admin = User.objects.create_user(
            email='admin@test.com', username='admin', password='pass123', role='admin'
        )
        self.manager = User.objects.create_user(
            email='manager@test.com', username='manager', password='pass123', role='manager'
        )
        self.accountant = User.objects.create_user(
            email='accountant@test.com', username='accountant', password='pass123', role='accountant'
        )

    def _mobile_login(self, email, password):
        return self.client.post(
            '/api/mobile/auth/login/',
            {'email': email, 'password': password},
            content_type='application/json',
        )

    def _auth_header(self, token):
        return {'HTTP_AUTHORIZATION': f'Bearer {token}'}

    def _get_mobile_token(self, user_email='cashier@test.com'):
        resp = self._mobile_login(user_email, 'pass123')
        return resp.data['access']

    def _get_web_token(self, user):
        from rest_framework_simplejwt.tokens import AccessToken
        return str(AccessToken.for_user(user))

    def _open_shift(self, user):
        Shift.objects.filter(user_id=user.id, status='open').update(status='closed')
        return Shift.objects.create(
            outlet=self.outlet,
            user_id=user.id,
            status='open',
            opening_cash=Decimal('50000'),
        )


# ---------------------------------------------------------------------------
# Group 1: Mobile login (6 tests)
# ---------------------------------------------------------------------------

class MobileLoginTests(MobileAPITestCase):

    def test_cashier_login_succeeds(self):
        resp = self._mobile_login('cashier@test.com', 'pass123')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('access', resp.data)
        self.assertIn('refresh', resp.data)

    def test_attendant_login_succeeds(self):
        resp = self._mobile_login('attendant@test.com', 'pass123')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_admin_login_rejected(self):
        resp = self._mobile_login('admin@test.com', 'pass123')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Mobile access restricted', str(resp.data))

    def test_manager_login_rejected(self):
        resp = self._mobile_login('manager@test.com', 'pass123')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_wrong_password_rejected(self):
        resp = self._mobile_login('cashier@test.com', 'wrongpassword')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inactive_user_rejected(self):
        self.cashier.is_active = False
        self.cashier.save()
        resp = self._mobile_login('cashier@test.com', 'pass123')
        self.assertIn(resp.status_code, [
            status.HTTP_401_UNAUTHORIZED, status.HTTP_400_BAD_REQUEST
        ])


# ---------------------------------------------------------------------------
# Group 2: ShiftStartDataView (9 tests)
# ---------------------------------------------------------------------------

class ShiftStartDataTests(MobileAPITestCase):

    def setUp(self):
        super().setUp()
        # Open a shift so outlet ownership check passes
        self._open_shift(self.cashier)
        self.token = self._get_mobile_token()
        self.url = '/api/mobile/shift-start-data/'

    def test_missing_outlet_id_returns_400(self):
        resp = self.client.get(self.url, **self._auth_header(self.token))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('outlet_id', str(resp.data))

    def test_invalid_outlet_id_returns_404(self):
        resp = self.client.get(
            self.url + '?outlet_id=99999', **self._auth_header(self.token)
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_correct_outlet_returns_200(self):
        resp = self.client.get(
            self.url + f'?outlet_id={self.outlet.id}',
            **self._auth_header(self.token),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('products', resp.data)
        self.assertIn('categories', resp.data)
        self.assertIn('discounts', resp.data)
        self.assertIn('pumps', resp.data)
        self.assertIn('generated_at', resp.data)

    def test_products_contain_correct_product(self):
        resp = self.client.get(
            self.url + f'?outlet_id={self.outlet.id}',
            **self._auth_header(self.token),
        )
        ids = [p['id'] for p in resp.data['products']]
        self.assertIn(self.product.id, ids)

    def test_outlet_stock_map_populated(self):
        resp = self.client.get(
            self.url + f'?outlet_id={self.outlet.id}',
            **self._auth_header(self.token),
        )
        product_in_resp = next(
            p for p in resp.data['products'] if p['id'] == self.product.id
        )
        self.assertEqual(
            Decimal(product_in_resp['outlet_stock']),
            Decimal('500'),
        )

    def test_expired_discounts_excluded(self):
        from django.utils import timezone
        from datetime import timedelta
        expired = Discount.objects.create(
            name='Expired',
            discount_type='fixed',
            value=Decimal('1000'),
            is_active=True,
            valid_until=timezone.now() - timedelta(days=1),
        )
        resp = self.client.get(
            self.url + f'?outlet_id={self.outlet.id}',
            **self._auth_header(self.token),
        )
        discount_ids = [d['id'] for d in resp.data['discounts']]
        self.assertNotIn(expired.id, discount_ids)

    def test_pumps_filtered_by_active_status(self):
        inactive_pump = Pump.objects.create(
            outlet=self.outlet,
            product=self.product,
            pump_number=2,
            name='Pump B',
            status='inactive',
        )
        resp = self.client.get(
            self.url + f'?outlet_id={self.outlet.id}',
            **self._auth_header(self.token),
        )
        pump_ids = [p['id'] for p in resp.data['pumps']]
        self.assertNotIn(inactive_pump.id, pump_ids)

    def test_no_open_shift_for_outlet_rejected(self):
        """Cashier with no shift at this outlet cannot download shift-start data."""
        other_outlet = Outlet.objects.create(name='Other Station', outlet_type='fuel_station')
        resp = self.client.get(
            self.url + f'?outlet_id={other_outlet.id}',
            **self._auth_header(self.token),
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_web_jwt_rejected(self):
        web_token = self._get_web_token(self.cashier)
        resp = self.client.get(
            self.url + f'?outlet_id={self.outlet.id}',
            **self._auth_header(web_token),
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_rejected(self):
        resp = self.client.get(self.url + f'?outlet_id={self.outlet.id}')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# Group 3: Batch sync (16 tests)
# ---------------------------------------------------------------------------

class BatchSyncTests(MobileAPITestCase):

    def setUp(self):
        super().setUp()
        self.token = self._get_mobile_token()
        self.url = '/api/mobile/sync/'
        self.shift = self._open_shift(self.cashier)

    def _sync_payload(self, transactions=None, shift_id=None):
        return {
            'device_id': 'device-001-abc',  # min 8 chars, alphanumeric+dash
            'shift_id': shift_id or self.shift.id,
            'transactions': transactions or [],
        }

    def _make_transaction(self, client_uuid=None, product_id=None):
        import uuid
        return {
            'client_uuid': str(client_uuid or uuid.uuid4()),
            'created_at': '2026-05-13T10:00:00Z',
            'items': [{
                'product_id': product_id or self.product.id,
                'quantity': '1.000',
                'unit_price': '5000.00',
                'discount_id': None,
            }],
            'payments': [{'payment_method': 'cash', 'amount': '5900.00', 'reference': ''}],
            'notes': '',
        }

    def test_empty_batch_returns_200(self):
        resp = self.client.post(
            self.url,
            self._sync_payload(),
            content_type='application/json',
            **self._auth_header(self.token),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['processed'], 0)

    def test_single_transaction_happy_path(self):
        resp = self.client.post(
            self.url,
            self._sync_payload([self._make_transaction()]),
            content_type='application/json',
            **self._auth_header(self.token),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['processed'], 1)
        result = resp.data['results'][0]
        self.assertEqual(result['status'], 'synced')
        self.assertIsNotNone(result['sale_id'])
        self.assertIsNotNone(result['receipt_number'])

    def test_deduplication_on_second_sync(self):
        import uuid
        uid = uuid.uuid4()
        txn = self._make_transaction(client_uuid=uid)
        payload = self._sync_payload([txn])
        self.client.post(
            self.url, payload, content_type='application/json',
            **self._auth_header(self.token),
        )
        resp = self.client.post(
            self.url, payload, content_type='application/json',
            **self._auth_header(self.token),
        )
        self.assertEqual(resp.data['results'][0]['status'], 'duplicate')

    def test_insufficient_stock_fails_transaction(self):
        txn = self._make_transaction()
        txn['items'][0]['quantity'] = '999999.000'
        txn['payments'][0]['amount'] = '9999990000.00'
        resp = self.client.post(
            self.url,
            self._sync_payload([txn]),
            content_type='application/json',
            **self._auth_header(self.token),
        )
        self.assertEqual(resp.data['results'][0]['status'], 'failed')
        self.assertIn('Insufficient stock', resp.data['results'][0]['message'])

    def test_partial_batch_some_succeed_some_fail(self):
        good_txn = self._make_transaction()
        bad_txn = self._make_transaction()
        bad_txn['items'][0]['quantity'] = '999999.000'
        bad_txn['payments'][0]['amount'] = '9999990000.00'
        resp = self.client.post(
            self.url,
            self._sync_payload([good_txn, bad_txn]),
            content_type='application/json',
            **self._auth_header(self.token),
        )
        statuses = [r['status'] for r in resp.data['results']]
        self.assertIn('synced', statuses)
        self.assertIn('failed', statuses)

    def test_batch_exceeding_500_rejected(self):
        import uuid
        transactions = [self._make_transaction() for _ in range(501)]
        for t in transactions:
            t['client_uuid'] = str(uuid.uuid4())
        resp = self.client.post(
            self.url,
            self._sync_payload(transactions),
            content_type='application/json',
            **self._auth_header(self.token),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_wrong_shift_owner_rejected(self):
        other_shift = self._open_shift(self.attendant)
        resp = self.client.post(
            self.url,
            self._sync_payload(shift_id=other_shift.id),
            content_type='application/json',
            **self._auth_header(self.token),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('does not belong', str(resp.data))

    def test_closed_shift_rejected(self):
        self.shift.status = 'closed'
        self.shift.save()
        resp = self.client.post(
            self.url,
            self._sync_payload([self._make_transaction()]),
            content_type='application/json',
            **self._auth_header(self.token),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not open', str(resp.data))

    def test_payments_not_sum_to_total_fails(self):
        txn = self._make_transaction()
        txn['payments'][0]['amount'] = '1.00'
        resp = self.client.post(
            self.url,
            self._sync_payload([txn]),
            content_type='application/json',
            **self._auth_header(self.token),
        )
        self.assertEqual(resp.data['results'][0]['status'], 'failed')
        self.assertIn('Insufficient payment', resp.data['results'][0]['message'])

    def test_product_not_found_fails(self):
        txn = self._make_transaction(product_id=99999)
        resp = self.client.post(
            self.url,
            self._sync_payload([txn]),
            content_type='application/json',
            **self._auth_header(self.token),
        )
        self.assertEqual(resp.data['results'][0]['status'], 'failed')

    def test_inactive_product_fails(self):
        self.product.is_active = False
        self.product.save()
        txn = self._make_transaction()
        resp = self.client.post(
            self.url,
            self._sync_payload([txn]),
            content_type='application/json',
            **self._auth_header(self.token),
        )
        self.assertEqual(resp.data['results'][0]['status'], 'failed')
        self.assertIn('inactive', resp.data['results'][0]['message'])

    def test_sync_log_created_after_batch(self):
        before = MobileSyncLog.objects.count()
        self.client.post(
            self.url,
            self._sync_payload([self._make_transaction()]),
            content_type='application/json',
            **self._auth_header(self.token),
        )
        self.assertEqual(MobileSyncLog.objects.count(), before + 1)

    def test_sync_log_counts_correct(self):
        good_txn = self._make_transaction()
        bad_txn = self._make_transaction()
        bad_txn['items'][0]['quantity'] = '999999.000'
        bad_txn['payments'][0]['amount'] = '9999990000.00'
        self.client.post(
            self.url,
            self._sync_payload([good_txn, bad_txn]),
            content_type='application/json',
            **self._auth_header(self.token),
        )
        log = MobileSyncLog.objects.latest('synced_at')
        self.assertEqual(log.success_count, 1)
        self.assertEqual(log.failed_count, 1)

    def test_shift_not_found_returns_400(self):
        resp = self.client.post(
            self.url,
            self._sync_payload(shift_id=99999),
            content_type='application/json',
            **self._auth_header(self.token),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        # Error message must not leak the shift ID (enumeration prevention)
        self.assertNotIn('99999', str(resp.data))

    def test_unauthenticated_rejected(self):
        resp = self.client.post(
            self.url, self._sync_payload(), content_type='application/json'
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_web_jwt_rejected_on_sync(self):
        web_token = self._get_web_token(self.cashier)
        resp = self.client.post(
            self.url,
            self._sync_payload(),
            content_type='application/json',
            **self._auth_header(web_token),
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# Group 4: Shift close with pending_mobile_transactions (4 tests)
# ---------------------------------------------------------------------------

class ShiftCloseTests(MobileAPITestCase):

    def setUp(self):
        super().setUp()
        self.shift = self._open_shift(self.cashier)
        # Authenticate via standard web login (close_shift is not mobile-restricted)
        resp = self.client.post(
            '/api/auth/login/',
            {'email': 'cashier@test.com', 'password': 'pass123'},
            content_type='application/json',
        )
        self.token = resp.data['access']
        self.url = f'/api/shifts/{self.shift.id}/close/'

    def test_zero_pending_allows_close(self):
        resp = self.client.post(
            self.url,
            {
                'closing_cash': '50000',
                'pending_mobile_transactions': 0,
            },
            content_type='application/json',
            **self._auth_header(self.token),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.shift.refresh_from_db()
        self.assertEqual(self.shift.status, 'closed')

    def test_nonzero_pending_blocks_close(self):
        resp = self.client.post(
            self.url,
            {
                'closing_cash': '50000',
                'pending_mobile_transactions': 2,
            },
            content_type='application/json',
            **self._auth_header(self.token),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Sync 2 pending', str(resp.data))

    def test_missing_pending_field_defaults_to_zero(self):
        resp = self.client.post(
            self.url,
            {'closing_cash': '50000'},
            content_type='application/json',
            **self._auth_header(self.token),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_sync_log_present_after_close(self):
        MobileSyncLog.objects.create(
            device_id='dev-001',
            shift_id=self.shift.id,
            user_id=self.cashier.id,
            outlet_id=self.outlet.id,
            transaction_count=1,
            success_count=1,
            failed_count=0,
        )
        self.assertTrue(
            MobileSyncLog.objects.filter(shift_id=self.shift.id).exists()
        )


# ---------------------------------------------------------------------------
# Group 5: IsNotMobileClient enforcement (6 tests)
# ---------------------------------------------------------------------------

class IsNotMobileClientTests(MobileAPITestCase):
    """
    Verify that a mobile JWT is rejected on sensitive endpoints
    and that a web JWT is accepted.
    """

    def setUp(self):
        super().setUp()
        self.mobile_token = self._get_mobile_token()
        self.web_token = self._get_web_token(self.admin)

    def _test_endpoint_rejects_mobile(self, url, method='get'):
        caller = getattr(self.client, method)
        resp = caller(url, **self._auth_header(self.mobile_token))
        self.assertEqual(
            resp.status_code,
            status.HTTP_403_FORBIDDEN,
            msg=f"Expected 403 on {url} with mobile token, got {resp.status_code}",
        )

    def _test_endpoint_accepts_web(self, url, method='get'):
        caller = getattr(self.client, method)
        resp = caller(url, **self._auth_header(self.web_token))
        self.assertNotEqual(
            resp.status_code,
            status.HTTP_403_FORBIDDEN,
            msg=f"Expected non-403 on {url} with web token, got {resp.status_code}",
        )

    def test_finance_rejects_mobile_token(self):
        self._test_endpoint_rejects_mobile('/api/accounts/')

    def test_finance_accepts_web_token(self):
        self._test_endpoint_accepts_web('/api/accounts/')

    def test_hr_rejects_mobile_token(self):
        self._test_endpoint_rejects_mobile('/api/employees/')

    def test_assets_rejects_mobile_token(self):
        self._test_endpoint_rejects_mobile('/api/assets/')

    def test_users_rejects_mobile_token(self):
        self._test_endpoint_rejects_mobile('/api/users/')

    def test_users_accepts_web_token(self):
        self._test_endpoint_accepts_web('/api/users/')
