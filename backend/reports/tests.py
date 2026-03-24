from decimal import Decimal
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from django.contrib.auth import get_user_model

from outlets.models import Outlet
from products.models import Category, Product
from sales.models import Discount, Shift, Sale, SaleItem, Payment
from inventory.models import StockAuditLog

User = get_user_model()


class ReportsTestBase(TenantTestCase):
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
        self.outlet2 = Outlet.objects.create(
            name='Branch', outlet_type='fuel_station',
        )
        self.category = Category.objects.create(
            name='Fuels', business_unit='fuel',
        )
        self.product = Product.objects.create(
            name='Petrol', sku='PET-001', category=self.category,
            cost_price=Decimal('3500.00'), selling_price=Decimal('4500.00'),
            tax_rate=Decimal('18.00'), stock_quantity=Decimal('1000.000'),
            reorder_level=Decimal('100.000'), unit='litre',
        )
        # Create a completed sale for testing
        self.shift = Shift.objects.create(
            outlet=self.outlet, user_id=self.cashier.id,
            opening_cash=Decimal('50000.00'),
        )
        self.sale = Sale.objects.create(
            receipt_number='OUT1-20260307-0001',
            outlet=self.outlet, shift=self.shift,
            cashier_id=self.cashier.id,
            subtotal=Decimal('45000.00'),
            tax_total=Decimal('8100.00'),
            discount_total=Decimal('0.00'),
            grand_total=Decimal('53100.00'),
        )
        SaleItem.objects.create(
            sale=self.sale, product=self.product,
            product_name='Petrol', unit_price=Decimal('4500.00'),
            quantity=Decimal('10.000'), tax_rate=Decimal('18.00'),
            tax_amount=Decimal('8100.00'), line_total=Decimal('53100.00'),
        )
        Payment.objects.create(
            sale=self.sale, payment_method='cash',
            amount=Decimal('53100.00'),
        )

    def _auth(self, user):
        response = self.client.post('/api/auth/login/', {
            'email': user.email, 'password': 'testpass123',
        })
        token = response.json()['access']
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {token}'


class SalesSummaryTest(ReportsTestBase):
    def test_sales_summary(self):
        self._auth(self.admin)
        response = self.client.get('/api/reports/sales-summary/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['total_sales'], 1)
        self.assertEqual(Decimal(data['total_revenue']), Decimal('53100.00'))

    def test_sales_summary_with_outlet_filter(self):
        self._auth(self.admin)
        response = self.client.get(f'/api/reports/sales-summary/?outlet={self.outlet.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['total_sales'], 1)

        # Different outlet should return 0
        response = self.client.get(f'/api/reports/sales-summary/?outlet={self.outlet2.id}')
        self.assertEqual(response.json()['total_sales'], 0)


class SalesByOutletTest(ReportsTestBase):
    def test_sales_by_outlet(self):
        self._auth(self.admin)
        response = self.client.get('/api/reports/sales-by-outlet/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['outlet_name'], 'Main Station')


class SalesByProductTest(ReportsTestBase):
    def test_sales_by_product(self):
        self._auth(self.admin)
        response = self.client.get('/api/reports/sales-by-product/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['product_name'], 'Petrol')
        self.assertEqual(Decimal(data[0]['total_quantity']), Decimal('10.000'))


class SalesByPaymentMethodTest(ReportsTestBase):
    def test_payment_method_breakdown(self):
        self._auth(self.admin)
        response = self.client.get('/api/reports/sales-by-payment-method/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['payment_method'], 'cash')
        self.assertEqual(Decimal(data[0]['total_amount']), Decimal('53100.00'))


class HourlySalesTest(ReportsTestBase):
    def test_hourly_sales(self):
        self._auth(self.admin)
        response = self.client.get('/api/reports/hourly-sales/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(len(data), 1)


class StockLevelsTest(ReportsTestBase):
    def test_stock_levels_aggregate(self):
        self._auth(self.admin)
        response = self.client.get('/api/reports/stock-levels/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(len(data), 1)


class DashboardTest(ReportsTestBase):
    def test_dashboard_admin(self):
        self._auth(self.admin)
        response = self.client.get('/api/reports/dashboard/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['today_sales'], 1)
        self.assertIn('today_revenue', data)
        self.assertIn('active_shifts', data)
        self.assertIn('low_stock_count', data)

    def test_dashboard_cashier_no_shift(self):
        # Close the existing shift first
        self.shift.status = 'closed'
        self.shift.save()

        self._auth(self.cashier)
        response = self.client.get('/api/reports/dashboard/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['today_sales'], 0)

    def test_unauthenticated_returns_401(self):
        response = self.client.get('/api/reports/dashboard/')
        self.assertEqual(response.status_code, 401)
