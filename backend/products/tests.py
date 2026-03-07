import json
from decimal import Decimal
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from django.contrib.auth import get_user_model
from .models import Category, Product

User = get_user_model()


class CategoryAPITest(TenantTestCase):
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

    def _auth(self, user):
        response = self.client.post('/api/auth/login/', {
            'email': user.email, 'password': 'testpass123',
        })
        token = response.json()['access']
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {token}'

    def test_admin_can_create_category(self):
        self._auth(self.admin)
        response = self.client.post('/api/categories/', {
            'name': 'Fuels', 'business_unit': 'fuel',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['name'], 'Fuels')

    def test_cashier_cannot_create_category(self):
        self._auth(self.cashier)
        response = self.client.post('/api/categories/', {
            'name': 'Snacks', 'business_unit': 'cafe',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_filter_by_business_unit(self):
        self._auth(self.admin)
        self.client.post('/api/categories/', {
            'name': 'Fuels', 'business_unit': 'fuel',
        }, content_type='application/json')
        self.client.post('/api/categories/', {
            'name': 'Drinks', 'business_unit': 'cafe',
        }, content_type='application/json')
        response = self.client.get('/api/categories/?business_unit=fuel')
        results = response.json()['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['name'], 'Fuels')

    def test_subcategory(self):
        self._auth(self.admin)
        resp = self.client.post('/api/categories/', {
            'name': 'Fuels', 'business_unit': 'fuel',
        }, content_type='application/json')
        parent_id = resp.json()['id']
        resp = self.client.post('/api/categories/', {
            'name': 'Petrol', 'business_unit': 'fuel', 'parent': parent_id,
        }, content_type='application/json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['parent'], parent_id)


class ProductAPITest(TenantTestCase):
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
        self.category = Category.objects.create(
            name='Fuels', business_unit='fuel',
        )

    def _auth(self, user):
        response = self.client.post('/api/auth/login/', {
            'email': user.email, 'password': 'testpass123',
        })
        token = response.json()['access']
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {token}'

    def _create_product(self, **overrides):
        data = {
            'name': 'Petrol',
            'sku': 'PET-001',
            'category': self.category.id,
            'cost_price': '3500.00',
            'selling_price': '4500.00',
            'tax_rate': '18.00',
            'stock_quantity': '1000.000',
            'reorder_level': '100.000',
            'unit': 'litre',
        }
        data.update(overrides)
        return self.client.post('/api/products/', data, content_type='application/json')

    def test_admin_can_create_product(self):
        self._auth(self.admin)
        response = self._create_product()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['name'], 'Petrol')
        self.assertEqual(response.json()['category_name'], 'Fuels')

    def test_cashier_cannot_create_product(self):
        self._auth(self.cashier)
        response = self._create_product()
        self.assertEqual(response.status_code, 403)

    def test_search_products(self):
        self._auth(self.admin)
        self._create_product(name='Petrol', sku='PET-001')
        self._create_product(name='Diesel', sku='DSL-001')
        response = self.client.get('/api/products/?search=Diesel')
        results = response.json()['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['name'], 'Diesel')

    def test_low_stock(self):
        self._auth(self.admin)
        self._create_product(
            name='Low Item', sku='LOW-001',
            stock_quantity='5.000', reorder_level='10.000',
        )
        self._create_product(
            name='OK Item', sku='OK-001',
            stock_quantity='500.000', reorder_level='10.000',
        )
        response = self.client.get('/api/products/low_stock/')
        results = response.json()['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['name'], 'Low Item')

    def test_adjust_stock(self):
        self._auth(self.admin)
        resp = self._create_product(stock_quantity='100.000')
        product_id = resp.json()['id']
        response = self.client.post(
            f'/api/products/{product_id}/adjust_stock/',
            {'quantity': '50.000', 'reason': 'Delivery received'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Decimal(response.json()['stock_quantity']), Decimal('150.000'))

    def test_adjust_stock_negative(self):
        self._auth(self.admin)
        resp = self._create_product(stock_quantity='100.000')
        product_id = resp.json()['id']
        response = self.client.post(
            f'/api/products/{product_id}/adjust_stock/',
            {'quantity': '-30.000', 'reason': 'Spillage'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Decimal(response.json()['stock_quantity']), Decimal('70.000'))

    def test_unique_sku(self):
        self._auth(self.admin)
        self._create_product(sku='DUP-001')
        response = self._create_product(name='Another', sku='DUP-001')
        self.assertEqual(response.status_code, 400)
