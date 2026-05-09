import json
from decimal import Decimal
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.management import call_command
from io import StringIO

from cafe.models import MenuCategory, MenuItem, MenuItemIngredient, MenuOrder, MenuOrderItem, WasteLog
from products.models import Category, Product
from outlets.models import Outlet
from inventory.models import OutletStock, StockAuditLog

User = get_user_model()


class CafeBaseTestCase(TenantTestCase):
    def setUp(self):
        self.client = TenantClient(self.tenant)
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
        self.attendant = User.objects.create_user(
            email='attendant@test.com', username='attendant',
            password='testpass123', role='attendant',
        )
        self.accountant = User.objects.create_user(
            email='accountant@test.com', username='accountant',
            password='testpass123', role='accountant',
        )
        
        # Base data
        self.outlet = Outlet.objects.create(name='Test Cafe Outlet', address='Test Location', outlet_type='cafe')
        self.prod_cat = Category.objects.create(name='Ingredients', business_unit='cafe')
        self.product1 = Product.objects.create(
            name='Beef Mince', sku='BEEF-001', category=self.prod_cat,
            cost_price='12000', selling_price='15000', stock_quantity='10.000', unit='kg'
        )
        self.product2 = Product.objects.create(
            name='Pastry Flour', sku='FLOUR-001', category=self.prod_cat,
            cost_price='6000', selling_price='8000', stock_quantity='20.000', unit='kg'
        )
        
        # Initial stock
        OutletStock.objects.create(outlet=self.outlet, product=self.product1, quantity='5.000')
        OutletStock.objects.create(outlet=self.outlet, product=self.product2, quantity='10.000')

    def _auth(self, user):
        response = self.client.post('/api/auth/login/', {
            'email': user.email, 'password': 'testpass123',
        })
        token = response.json()['access']
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {token}'


class MenuCategoryAPITest(CafeBaseTestCase):
    def test_create_menu_category_as_admin(self):
        self._auth(self.admin)
        response = self.client.post('/api/cafe/menu-categories/', {
            'name': 'Pastries', 'description': 'Fresh daily bakes', 'display_order': 2
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(MenuCategory.objects.count(), 1)

    def test_create_menu_category_as_cashier_forbidden(self):
        self._auth(self.cashier)
        response = self.client.post('/api/cafe/menu-categories/', {
            'name': 'Drinks'
        }, content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_list_menu_categories_paginated(self):
        MenuCategory.objects.create(name='Cat 1', display_order=1)
        MenuCategory.objects.create(name='Cat 2', display_order=2)
        self._auth(self.cashier)
        response = self.client.get('/api/cafe/menu-categories/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['results']), 2)

    def test_inactive_category_excluded_from_listing(self):
        MenuCategory.objects.create(name='Active', is_active=True)
        MenuCategory.objects.create(name='Inactive', is_active=False)
        self._auth(self.cashier)
        response = self.client.get('/api/cafe/menu-categories/')
        self.assertEqual(len(response.json()['results']), 1)
        self.assertEqual(response.json()['results'][0]['name'], 'Active')


class MenuItemAPITest(CafeBaseTestCase):
    def setUp(self):
        super().setUp()
        self.category = MenuCategory.objects.create(name='Hot Food')

    def test_create_menu_item_no_bom(self):
        self._auth(self.admin)
        response = self.client.post('/api/cafe/menu-items/', {
            'name': 'Coffee', 'category_id': self.category.id, 'price': '3000', 'has_bom': False
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Decimal(response.json()['cost_price']), Decimal('0'))

    def test_create_menu_item_with_bom_flag(self):
        self._auth(self.admin)
        response = self.client.post('/api/cafe/menu-items/', {
            'name': 'Beef Pie', 'category_id': self.category.id, 'price': '5000', 'has_bom': True
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()['has_bom'])

    def test_update_bom_replaces_ingredients(self):
        self._auth(self.admin)
        item = MenuItem.objects.create(name='Beef Pie', category=self.category, price='5000', has_bom=True)
        # Add initial ingredient
        MenuItemIngredient.objects.create(menu_item=item, product=self.product1, quantity_per_serving='0.100', unit='kg')
        
        response = self.client.post(f'/api/cafe/menu-items/{item.id}/update-bom/', {
            'ingredients': [
                {'product_id': self.product1.id, 'quantity_per_serving': '0.150', 'unit': 'kg'},
                {'product_id': self.product2.id, 'quantity_per_serving': '0.050', 'unit': 'kg'}
            ]
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(MenuItemIngredient.objects.filter(menu_item=item).count(), 2)
        # Cost: (0.150 * 12000) + (0.050 * 6000) = 1800 + 300 = 2100
        self.assertEqual(Decimal(response.json()['cost_price']), Decimal('2100'))

    def test_cost_endpoint_returns_breakdown(self):
        self._auth(self.admin)
        item = MenuItem.objects.create(name='Beef Pie', category=self.category, price='5000', has_bom=True)
        MenuItemIngredient.objects.create(menu_item=item, product=self.product1, quantity_per_serving='0.150', unit='kg')
        MenuItemIngredient.objects.create(menu_item=item, product=self.product2, quantity_per_serving='0.050', unit='kg')
        item.recompute_cost_price()
        
        response = self.client.get(f'/api/cafe/menu-items/{item.id}/cost/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['cost_price'], '2100.00')
        self.assertEqual(len(response.json()['ingredients']), 2)

    def test_cost_endpoint_requires_manager(self):
        item = MenuItem.objects.create(name='Beef Pie', category=self.category, price='5000')
        self._auth(self.cashier)
        response = self.client.get(f'/api/cafe/menu-items/{item.id}/cost/')
        self.assertEqual(response.status_code, 403)

    def test_menu_item_search_by_name(self):
        MenuItem.objects.create(name='Apple Pie', category=self.category, price='4000')
        MenuItem.objects.create(name='Beef Pie', category=self.category, price='5000')
        self._auth(self.cashier)
        response = self.client.get('/api/cafe/menu-items/?search=Apple')
        self.assertEqual(len(response.json()['results']), 1)

    def test_menu_item_filter_by_category(self):
        cat2 = MenuCategory.objects.create(name='Drinks')
        MenuItem.objects.create(name='Pie', category=self.category, price='5000')
        MenuItem.objects.create(name='Juice', category=cat2, price='3000')
        self._auth(self.cashier)
        response = self.client.get(f'/api/cafe/menu-items/?category={cat2.id}')
        self.assertEqual(len(response.json()['results']), 1)
        self.assertEqual(response.json()['results'][0]['name'], 'Juice')


class MenuOrderAPITest(CafeBaseTestCase):
    def setUp(self):
        super().setUp()
        self.category = MenuCategory.objects.create(name='Hot Food')
        self.item_bom = MenuItem.objects.create(name='Beef Pie', category=self.category, price='5000', has_bom=True)
        MenuItemIngredient.objects.create(menu_item=self.item_bom, product=self.product1, quantity_per_serving='0.150', unit='kg')
        self.item_no_bom = MenuItem.objects.create(name='Soda', category=self.category, price='2000', has_bom=False)

    def test_create_dine_in_order_deducts_stock(self):
        self._auth(self.cashier)
        initial_stock = OutletStock.objects.get(outlet=self.outlet, product=self.product1).quantity
        
        response = self.client.post('/api/cafe/orders/', {
            'order_type': 'dine_in',
            'table_number': 'T1',
            'outlet_id': self.outlet.id,
            'items': [{'menu_item_id': self.item_bom.id, 'quantity': 2}]
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 201)
        new_stock = OutletStock.objects.get(outlet=self.outlet, product=self.product1).quantity
        # Deduct 2 * 0.150 = 0.300
        self.assertEqual(new_stock, initial_stock - Decimal('0.300'))
        
        # Check audit log
        self.assertTrue(StockAuditLog.objects.filter(reference_type='menu_order').exists())

    def test_create_order_insufficient_stock_returns_400(self):
        self._auth(self.cashier)
        # Current stock of product1 is 5.000. Required: 40 * 0.150 = 6.000
        response = self.client.post('/api/cafe/orders/', {
            'order_type': 'takeaway',
            'outlet_id': self.outlet.id,
            'items': [{'menu_item_id': self.item_bom.id, 'quantity': 40}]
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('shortages', response.json())

    def test_create_order_unavailable_item_returns_400(self):
        self.item_bom.is_available = False
        self.item_bom.save()
        self._auth(self.cashier)
        response = self.client.post('/api/cafe/orders/', {
            'order_type': 'dine_in',
            'outlet_id': self.outlet.id,
            'items': [{'menu_item_id': self.item_bom.id, 'quantity': 1}]
        }, content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_cancel_order_restores_bom_stock(self):
        self._auth(self.cashier)
        # Create order
        resp = self.client.post('/api/cafe/orders/', {
            'order_type': 'dine_in',
            'outlet_id': self.outlet.id,
            'items': [{'menu_item_id': self.item_bom.id, 'quantity': 2}]
        }, content_type='application/json')
        order_id = resp.json()['id']
        stock_after_order = OutletStock.objects.get(outlet=self.outlet, product=self.product1).quantity
        
        # Cancel order
        response = self.client.post(f'/api/cafe/orders/{order_id}/status/', {
            'status': 'cancelled'
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        restored_stock = OutletStock.objects.get(outlet=self.outlet, product=self.product1).quantity
        self.assertEqual(restored_stock, stock_after_order + Decimal('0.300'))


class WasteLogAPITest(CafeBaseTestCase):
    def test_create_waste_log_auto_computes_cost_value(self):
        self._auth(self.admin)
        response = self.client.post('/api/cafe/waste-logs/', {
            'product_id': self.product1.id,
            'quantity': '0.500',
            'unit': 'kg',
            'reason': 'expired'
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 201)
        # Cost: 0.5 * 12000 = 6000
        self.assertEqual(Decimal(response.json()['cost_value']), Decimal('6000'))


class ExpiryCommandTest(CafeBaseTestCase):
    def test_check_cafe_expiry_sends_notification_threshold(self):
        # Create 3 expired logs for the same product
        for _ in range(3):
            WasteLog.objects.create(
                product=self.product1, quantity=Decimal('0.1'), unit='kg',
                reason='expired', recorded_by_id=self.admin.id
            )
            
        out = StringIO()
        call_command('check_cafe_expiry', stdout=out)
        self.assertIn('Trend found: Beef Mince', out.getvalue())
        
        # Check if notification was created for admin/manager
        from notifications.models import Notification
        self.assertTrue(Notification.objects.filter(notification_type='expiry_alert').exists())
