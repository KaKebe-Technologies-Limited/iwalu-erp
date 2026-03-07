import json
from decimal import Decimal
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from django.contrib.auth import get_user_model

from outlets.models import Outlet
from products.models import Category, Product
from .models import Discount, Shift, Sale

User = get_user_model()


class SalesTestBase(TenantTestCase):
    """Base class with common setup for sales tests."""

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
        self.accountant = User.objects.create_user(
            email='acct@test.com', username='accountant',
            password='testpass123', role='accountant',
        )
        self.outlet = Outlet.objects.create(
            name='Main Station', outlet_type='fuel_station',
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

    def _auth(self, user):
        response = self.client.post('/api/auth/login/', {
            'email': user.email, 'password': 'testpass123',
        })
        token = response.json()['access']
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {token}'

    def _open_shift(self, user=None):
        if user:
            self._auth(user)
        response = self.client.post('/api/shifts/open/', {
            'outlet': self.outlet.id,
            'opening_cash': '50000.00',
        }, content_type='application/json')
        return response


class DiscountAPITest(SalesTestBase):
    def test_admin_can_create_discount(self):
        self._auth(self.admin)
        response = self.client.post('/api/discounts/', {
            'name': 'Staff 10%',
            'discount_type': 'percentage',
            'value': '10.00',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)

    def test_cashier_cannot_create_discount(self):
        self._auth(self.cashier)
        response = self.client.post('/api/discounts/', {
            'name': 'Hack', 'discount_type': 'fixed', 'value': '999.00',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_list_discounts(self):
        self._auth(self.cashier)
        response = self.client.get('/api/discounts/')
        self.assertEqual(response.status_code, 200)


class ShiftAPITest(SalesTestBase):
    def test_open_shift(self):
        self._auth(self.cashier)
        response = self._open_shift()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['status'], 'open')

    def test_cannot_open_duplicate_shift(self):
        self._auth(self.cashier)
        self._open_shift()
        response = self._open_shift()
        self.assertEqual(response.status_code, 400)

    def test_close_shift(self):
        self._auth(self.cashier)
        resp = self._open_shift()
        shift_id = resp.json()['id']
        response = self.client.post(
            f'/api/shifts/{shift_id}/close/',
            {'closing_cash': '50000.00'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'closed')

    def test_my_current_shift(self):
        self._auth(self.cashier)
        self._open_shift()
        response = self.client.get('/api/shifts/my_current/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'open')

    def test_no_current_shift(self):
        self._auth(self.cashier)
        response = self.client.get('/api/shifts/my_current/')
        self.assertEqual(response.status_code, 404)

    def test_accountant_cannot_open_shift(self):
        self._auth(self.accountant)
        response = self._open_shift()
        self.assertEqual(response.status_code, 403)


class CheckoutAPITest(SalesTestBase):
    def _checkout(self, items=None, payments=None, **kwargs):
        if items is None:
            items = [{'product_id': self.product.id, 'quantity': '10.000'}]
        if payments is None:
            payments = [{'payment_method': 'cash', 'amount': '100000.00'}]
        data = {'items': items, 'payments': payments}
        data.update(kwargs)
        return self.client.post(
            '/api/checkout/', data, content_type='application/json',
        )

    def test_single_item_cash(self):
        self._auth(self.cashier)
        self._open_shift()
        response = self._checkout()
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn('receipt_number', data)
        self.assertEqual(data['status'], 'completed')
        # 10 litres * 4500 = 45000 subtotal
        self.assertEqual(Decimal(data['subtotal']), Decimal('45000.00'))
        # Tax: 45000 * 18% = 8100
        self.assertEqual(Decimal(data['tax_total']), Decimal('8100.00'))
        # Grand total: 45000 + 8100 = 53100
        self.assertEqual(Decimal(data['grand_total']), Decimal('53100.00'))

    def test_stock_deduction(self):
        self._auth(self.cashier)
        self._open_shift()
        self._checkout(
            items=[{'product_id': self.product.id, 'quantity': '10.000'}],
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, Decimal('990.000'))

    def test_insufficient_stock(self):
        self._auth(self.cashier)
        self._open_shift()
        response = self._checkout(
            items=[{'product_id': self.product.id, 'quantity': '5000.000'}],
        )
        self.assertEqual(response.status_code, 400)

    def test_insufficient_payment(self):
        self._auth(self.cashier)
        self._open_shift()
        response = self._checkout(
            payments=[{'payment_method': 'cash', 'amount': '1.00'}],
        )
        self.assertEqual(response.status_code, 400)

    def test_multi_item_split_payment(self):
        product2 = Product.objects.create(
            name='Diesel', sku='DSL-001', category=self.category,
            cost_price=Decimal('3200.00'), selling_price=Decimal('4200.00'),
            tax_rate=Decimal('18.00'), stock_quantity=Decimal('500.000'),
            unit='litre',
        )
        self._auth(self.cashier)
        self._open_shift()
        response = self._checkout(
            items=[
                {'product_id': self.product.id, 'quantity': '5.000'},
                {'product_id': product2.id, 'quantity': '10.000'},
            ],
            payments=[
                {'payment_method': 'cash', 'amount': '50000.00'},
                {'payment_method': 'mobile_money', 'amount': '50000.00',
                 'reference': 'MM-12345'},
            ],
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(len(data['items']), 2)
        self.assertEqual(len(data['payments']), 2)

    def test_percentage_discount(self):
        discount = Discount.objects.create(
            name='10% Off', discount_type='percentage', value=Decimal('10.00'),
        )
        self._auth(self.cashier)
        self._open_shift()
        response = self._checkout(discount_id=discount.id)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertGreater(Decimal(data['discount_total']), Decimal('0'))

    def test_fixed_discount(self):
        discount = Discount.objects.create(
            name='5000 Off', discount_type='fixed', value=Decimal('5000.00'),
        )
        self._auth(self.cashier)
        self._open_shift()
        response = self._checkout(discount_id=discount.id)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(Decimal(data['discount_total']), Decimal('5000.00'))

    def test_no_open_shift(self):
        self._auth(self.cashier)
        response = self._checkout()
        self.assertEqual(response.status_code, 400)

    def test_accountant_blocked(self):
        self._auth(self.accountant)
        response = self._checkout()
        self.assertEqual(response.status_code, 403)

    def test_void_sale_restores_stock(self):
        self._auth(self.cashier)
        self._open_shift()
        resp = self._checkout(
            items=[{'product_id': self.product.id, 'quantity': '20.000'}],
            payments=[{'payment_method': 'cash', 'amount': '110000.00'}],
        )
        sale_id = resp.json()['id']
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, Decimal('980.000'))

        self._auth(self.admin)
        response = self.client.post(f'/api/sales/{sale_id}/void/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'voided')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, Decimal('1000.000'))

    def test_shift_expected_cash(self):
        self._auth(self.cashier)
        resp = self._open_shift()
        shift_id = resp.json()['id']
        # Make a cash sale
        self._checkout(
            items=[{'product_id': self.product.id, 'quantity': '10.000'}],
            payments=[{'payment_method': 'cash', 'amount': '53100.00'}],
        )
        # Close shift
        response = self.client.post(
            f'/api/shifts/{shift_id}/close/',
            {'closing_cash': '103100.00'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Expected = opening (50000) + cash payments (53100)
        self.assertEqual(Decimal(data['expected_cash']), Decimal('103100.00'))
