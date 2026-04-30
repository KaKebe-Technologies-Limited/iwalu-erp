from decimal import Decimal
from unittest.mock import patch
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from django.contrib.auth import get_user_model

from outlets.models import Outlet
from products.models import Category, Product
from sales.models import Sale, SaleItem, Payment, Shift
from .models import EfrisConfig, FiscalInvoice
from .providers import (
    MockProvider, WeafProvider, ProviderError, ProviderRejectedError,
    FiscalResult, get_provider_class,
)
from . import services

User = get_user_model()


class FiscalizationTestBase(TenantTestCase):
    def setUp(self):
        self.client = TenantClient(self.tenant)
        self.admin = User.objects.create_user(
            email='admin@test.com', username='admin',
            password='testpass123', role='admin',
        )
        self.cashier = User.objects.create_user(
            email='cashier@test.com', username='cashier',
            password='testpass123', role='cashier',
        )
        self.outlet = Outlet.objects.create(
            name='Main Station', outlet_type='fuel_station',
        )
        self.category = Category.objects.create(name='Fuels', business_unit='fuel')
        self.product = Product.objects.create(
            name='Petrol', sku='PET-001', category=self.category,
            cost_price=Decimal('3500.00'), selling_price=Decimal('4500.00'),
            tax_rate=Decimal('18.00'), stock_quantity=Decimal('1000.000'),
            unit='litre',
        )
        self.shift = Shift.objects.create(
            outlet=self.outlet, user_id=self.cashier.pk,
            opening_cash=Decimal('100000.00'),
        )

    def _auth(self, user):
        response = self.client.post('/api/auth/login/', {
            'email': user.email, 'password': 'testpass123',
        })
        token = response.json()['access']
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {token}'

    def _create_sale(self, grand_total='5310.00'):
        sale = Sale.objects.create(
            receipt_number='TEST-001',
            outlet=self.outlet,
            shift=self.shift,
            cashier_id=self.cashier.pk,
            subtotal=Decimal('4500.00'),
            tax_total=Decimal('810.00'),
            discount_total=Decimal('0.00'),
            grand_total=Decimal(grand_total),
            status='completed',
        )
        SaleItem.objects.create(
            sale=sale,
            product=self.product,
            product_name=self.product.name,
            unit_price=Decimal('4500.00'),
            quantity=Decimal('1.000'),
            tax_rate=Decimal('18.00'),
            tax_amount=Decimal('810.00'),
            line_total=Decimal('5310.00'),
        )
        Payment.objects.create(
            sale=sale, payment_method='cash', amount=Decimal(grand_total),
        )
        return sale


class ConfigTests(FiscalizationTestBase):

    def test_get_creates_default(self):
        config = services.get_config()
        self.assertIsNotNone(config)
        self.assertEqual(config.provider, 'mock')
        self.assertFalse(config.is_enabled)

    def test_singleton_enforcement(self):
        services.get_config()
        # Save another — pk forced to 1
        EfrisConfig(tin='DUP').save()
        self.assertEqual(EfrisConfig.objects.count(), 1)


class ProviderFactoryTests(FiscalizationTestBase):

    def test_get_provider_class_mock(self):
        self.assertIs(get_provider_class('mock'), MockProvider)

    def test_get_provider_class_weaf(self):
        self.assertIs(get_provider_class('weaf'), WeafProvider)

    def test_get_provider_class_unknown(self):
        with self.assertRaises(ValueError):
            get_provider_class('foo')


class MockProviderTests(FiscalizationTestBase):

    def test_mock_returns_fake_fdn(self):
        config = services.get_config()
        provider = MockProvider(config)
        result = provider.submit_invoice({'invoiceReference': 'T-001'})
        self.assertTrue(result.success)
        self.assertTrue(result.fdn.startswith('MOCK-'))
        self.assertTrue(result.qr_code.startswith('https://'))

    def test_mock_is_deterministic_per_reference(self):
        config = services.get_config()
        provider = MockProvider(config)
        r1 = provider.submit_invoice({'invoiceReference': 'SAME-REF'})
        r2 = provider.submit_invoice({'invoiceReference': 'SAME-REF'})
        self.assertEqual(r1.fdn, r2.fdn)


class WeafProviderTests(FiscalizationTestBase):

    def test_weaf_requires_api_key(self):
        config = services.get_config()
        config.provider = 'weaf'
        config.weaf_api_key = ''
        with self.assertRaises(ProviderError):
            WeafProvider(config)

    def test_weaf_requires_base_url(self):
        config = services.get_config()
        config.provider = 'weaf'
        config.weaf_api_key = 'test-key'
        config.weaf_base_url = ''
        with self.assertRaises(ProviderError):
            WeafProvider(config)

    @patch('fiscalization.providers.weaf.requests.post')
    def test_weaf_success_maps_response(self, mock_post):
        config = services.get_config()
        config.provider = 'weaf'
        config.weaf_api_key = 'test-key'
        config.weaf_base_url = 'https://sandbox.weaf.test'
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'fdn': 'WEAF-12345',
            'invoiceId': 'INV-99',
            'verificationCode': 'ABC123',
            'qrCode': 'https://efris/verify?x=1',
        }
        provider = WeafProvider(config)
        result = provider.submit_invoice({'invoiceReference': 'T-001'})
        self.assertTrue(result.success)
        self.assertEqual(result.fdn, 'WEAF-12345')

    @patch('fiscalization.providers.weaf.requests.post')
    def test_weaf_4xx_raises_rejected(self, mock_post):
        config = services.get_config()
        config.provider = 'weaf'
        config.weaf_api_key = 'test-key'
        config.weaf_base_url = 'https://sandbox.weaf.test'
        mock_post.return_value.status_code = 400
        mock_post.return_value.text = 'Invalid TIN'
        provider = WeafProvider(config)
        with self.assertRaises(ProviderRejectedError):
            provider.submit_invoice({})

    @patch('fiscalization.providers.weaf.requests.post')
    def test_weaf_5xx_raises_retryable(self, mock_post):
        config = services.get_config()
        config.provider = 'weaf'
        config.weaf_api_key = 'test-key'
        config.weaf_base_url = 'https://sandbox.weaf.test'
        mock_post.return_value.status_code = 503
        mock_post.return_value.text = 'Service Unavailable'
        provider = WeafProvider(config)
        with self.assertRaises(ProviderError):
            provider.submit_invoice({})


class PayloadBuildTests(FiscalizationTestBase):

    def test_build_payload_shape(self):
        sale = self._create_sale()
        config = services.get_config()
        config.tin = '1234567890'
        config.legal_name = 'Test Fuels Ltd'
        payload = services.build_payload(sale, config)

        self.assertEqual(payload['invoiceReference'], 'TEST-001')
        self.assertEqual(payload['seller']['tin'], '1234567890')
        self.assertEqual(payload['seller']['legalName'], 'Test Fuels Ltd')
        self.assertEqual(payload['buyer']['type'], 'FINAL_CONSUMER')
        self.assertEqual(len(payload['items']), 1)
        self.assertEqual(payload['items'][0]['code'], 'PET-001')
        self.assertEqual(payload['totals']['grandTotal'], '5310.00')
        self.assertEqual(len(payload['payments']), 1)


class SubmitSaleTests(FiscalizationTestBase):

    def test_disabled_returns_skipped(self):
        sale = self._create_sale()
        # Config defaults to is_enabled=False
        fi = services.submit_sale_for_fiscalization(sale)
        self.assertEqual(fi.status, 'skipped')

    def test_mock_provider_accepts(self):
        config = services.get_config()
        config.is_enabled = True
        config.provider = 'mock'
        config.tin = '1000000000'
        config.save()

        sale = self._create_sale()
        fi = services.submit_sale_for_fiscalization(sale)
        self.assertEqual(fi.status, 'accepted')
        self.assertTrue(fi.fdn.startswith('MOCK-'))
        self.assertTrue(fi.is_fiscalized)

    def test_rejected_provider_marks_rejected(self):
        config = services.get_config()
        config.is_enabled = True
        config.save()
        sale = self._create_sale()

        with patch.object(MockProvider, 'submit_invoice',
                          side_effect=ProviderRejectedError('Invalid TIN')):
            fi = services.submit_sale_for_fiscalization(sale)
        self.assertEqual(fi.status, 'rejected')
        self.assertIn('Invalid TIN', fi.error_message)

    def test_transient_failure_marks_failed(self):
        config = services.get_config()
        config.is_enabled = True
        config.save()
        sale = self._create_sale()

        with patch.object(MockProvider, 'submit_invoice',
                          side_effect=ProviderError('Network down')):
            fi = services.submit_sale_for_fiscalization(sale)
        self.assertEqual(fi.status, 'failed')
        self.assertIn('Network down', fi.error_message)

    def test_unexpected_exception_marks_failed(self):
        config = services.get_config()
        config.is_enabled = True
        config.save()
        sale = self._create_sale()

        with patch.object(MockProvider, 'submit_invoice',
                          side_effect=RuntimeError('boom')):
            fi = services.submit_sale_for_fiscalization(sale)
        self.assertEqual(fi.status, 'failed')
        self.assertIn('boom', fi.error_message)


class RetryFailedTests(FiscalizationTestBase):

    def _make_failed_fi(self, retry_count=0):
        config = services.get_config()
        config.is_enabled = True
        config.save()
        sale = self._create_sale()
        return FiscalInvoice.objects.create(
            sale=sale, status='failed', provider='mock',
            request_payload={'invoiceReference': 'TEST-001'},
            retry_count=retry_count,
            error_message='Earlier failure',
        )

    def test_retry_success(self):
        self._make_failed_fi()
        stats = services.retry_failed_invoices()
        self.assertEqual(stats['retried'], 1)
        self.assertEqual(stats['succeeded'], 1)

    def test_retry_exhausted_skipped(self):
        self._make_failed_fi(retry_count=5)  # already at MAX
        stats = services.retry_failed_invoices()
        self.assertEqual(stats['retried'], 0)


class GetFiscalDataTests(FiscalizationTestBase):

    def test_returns_none_when_no_invoice(self):
        sale = self._create_sale()
        self.assertIsNone(services.get_fiscal_data(sale))

    def test_returns_none_when_not_accepted(self):
        sale = self._create_sale()
        FiscalInvoice.objects.create(
            sale=sale, status='failed', provider='mock',
        )
        self.assertIsNone(services.get_fiscal_data(sale))

    def test_returns_data_when_fiscalized(self):
        sale = self._create_sale()
        FiscalInvoice.objects.create(
            sale=sale, status='accepted', provider='mock',
            fdn='MOCK-ABC', invoice_id='INV-1',
            verification_code='CODE', qr_code='https://x',
        )
        data = services.get_fiscal_data(sale)
        self.assertIsNotNone(data)
        self.assertEqual(data['fdn'], 'MOCK-ABC')
        self.assertEqual(data['qr_code'], 'https://x')


class EfrisConfigAPITests(FiscalizationTestBase):

    def test_get_config(self):
        self._auth(self.admin)
        response = self.client.get('/api/fiscalization/config/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['provider'], 'mock')

    def test_update_config_admin(self):
        services.get_config()
        self._auth(self.admin)
        response = self.client.patch(
            '/api/fiscalization/config/1/',
            data={'tin': '1234567890', 'is_enabled': True},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['tin'], '1234567890')
        self.assertTrue(response.json()['is_enabled'])

    def test_update_config_cashier_denied(self):
        self._auth(self.cashier)
        response = self.client.patch(
            '/api/fiscalization/config/1/',
            data={'tin': 'hack'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)

    def test_api_key_not_leaked_in_get(self):
        config = services.get_config()
        config.weaf_api_key = 'super-secret'
        config.save()
        self._auth(self.admin)
        response = self.client.get('/api/fiscalization/config/')
        self.assertNotIn('weaf_api_key', response.json())


class FiscalInvoiceAPITests(FiscalizationTestBase):

    def test_list_invoices(self):
        sale = self._create_sale()
        FiscalInvoice.objects.create(
            sale=sale, status='accepted', provider='mock', fdn='MOCK-X',
        )
        self._auth(self.admin)
        response = self.client.get('/api/fiscalization/invoices/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)

    def test_retry_failed_invoice(self):
        config = services.get_config()
        config.is_enabled = True
        config.save()
        sale = self._create_sale()
        fi = FiscalInvoice.objects.create(
            sale=sale, status='failed', provider='mock',
            request_payload={'invoiceReference': 'TEST-001'},
        )
        self._auth(self.admin)
        response = self.client.post(f'/api/fiscalization/invoices/{fi.pk}/retry/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'accepted')

    def test_retry_non_failed_rejected(self):
        sale = self._create_sale()
        fi = FiscalInvoice.objects.create(
            sale=sale, status='accepted', provider='mock', fdn='MOCK-X',
        )
        self._auth(self.admin)
        response = self.client.post(f'/api/fiscalization/invoices/{fi.pk}/retry/')
        self.assertEqual(response.status_code, 400)
