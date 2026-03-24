from decimal import Decimal
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from django.contrib.auth import get_user_model

from outlets.models import Outlet
from products.models import Category, Product
from .models import (
    Supplier, OutletStock, PurchaseOrder, PurchaseOrderItem,
    StockTransfer, StockTransferItem, StockAuditLog,
)

User = get_user_model()


class InventoryTestBase(TenantTestCase):
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
        self.outlet1 = Outlet.objects.create(
            name='Main Station', outlet_type='fuel_station',
        )
        self.outlet2 = Outlet.objects.create(
            name='Branch Station', outlet_type='fuel_station',
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
        self.product2 = Product.objects.create(
            name='Diesel', sku='DSL-001', category=self.category,
            cost_price=Decimal('3200.00'), selling_price=Decimal('4200.00'),
            tax_rate=Decimal('18.00'), stock_quantity=Decimal('500.000'),
            reorder_level=Decimal('50.000'), unit='litre',
        )

    def _auth(self, user):
        response = self.client.post('/api/auth/login/', {
            'email': user.email, 'password': 'testpass123',
        })
        token = response.json()['access']
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {token}'


class SupplierAPITest(InventoryTestBase):
    def test_admin_can_create_supplier(self):
        self._auth(self.admin)
        response = self.client.post('/api/suppliers/', {
            'name': 'Total Energies',
            'contact_person': 'John Doe',
            'email': 'john@total.com',
            'phone': '+256700000000',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['name'], 'Total Energies')

    def test_cashier_cannot_create_supplier(self):
        self._auth(self.cashier)
        response = self.client.post('/api/suppliers/', {
            'name': 'Shell',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_cashier_can_list_suppliers(self):
        Supplier.objects.create(name='Total Energies')
        self._auth(self.cashier)
        response = self.client.get('/api/suppliers/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)

    def test_search_suppliers(self):
        Supplier.objects.create(name='Total Energies')
        Supplier.objects.create(name='Shell Uganda')
        self._auth(self.admin)
        response = self.client.get('/api/suppliers/?search=shell')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)


class PurchaseOrderAPITest(InventoryTestBase):
    def _create_supplier(self):
        return Supplier.objects.create(name='Total Energies')

    def _create_po(self, supplier=None):
        if not supplier:
            supplier = self._create_supplier()
        self._auth(self.admin)
        return self.client.post('/api/purchase-orders/', {
            'supplier_id': supplier.id,
            'outlet_id': self.outlet1.id,
            'items': [
                {
                    'product_id': self.product.id,
                    'quantity_ordered': '100.000',
                    'unit_cost': '3500.00',
                },
                {
                    'product_id': self.product2.id,
                    'quantity_ordered': '50.000',
                    'unit_cost': '3200.00',
                },
            ],
        }, content_type='application/json')

    def test_create_po_with_items(self):
        response = self._create_po()
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data['po_number'].startswith('PO-'))
        self.assertEqual(data['status'], 'draft')
        self.assertEqual(len(data['items']), 2)
        # 100 * 3500 + 50 * 3200 = 510000
        self.assertEqual(Decimal(data['total_cost']), Decimal('510000.00'))

    def test_submit_po(self):
        resp = self._create_po()
        po_id = resp.json()['id']
        response = self.client.post(f'/api/purchase-orders/{po_id}/submit/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'submitted')

    def test_cannot_submit_non_draft(self):
        resp = self._create_po()
        po_id = resp.json()['id']
        self.client.post(f'/api/purchase-orders/{po_id}/submit/')
        response = self.client.post(f'/api/purchase-orders/{po_id}/submit/')
        self.assertEqual(response.status_code, 400)

    def test_receive_po_full(self):
        resp = self._create_po()
        po_id = resp.json()['id']
        items = resp.json()['items']
        self.client.post(f'/api/purchase-orders/{po_id}/submit/')

        response = self.client.post(
            f'/api/purchase-orders/{po_id}/receive/',
            {'items': [
                {'po_item_id': items[0]['id'], 'quantity_received': '100.000'},
                {'po_item_id': items[1]['id'], 'quantity_received': '50.000'},
            ]},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'received')

        # Check stock updated
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, Decimal('1100.000'))
        self.product2.refresh_from_db()
        self.assertEqual(self.product2.stock_quantity, Decimal('550.000'))

        # Check OutletStock created
        os1 = OutletStock.objects.get(outlet=self.outlet1, product=self.product)
        self.assertEqual(os1.quantity, Decimal('100.000'))

    def test_receive_po_partial(self):
        resp = self._create_po()
        po_id = resp.json()['id']
        items = resp.json()['items']
        self.client.post(f'/api/purchase-orders/{po_id}/submit/')

        response = self.client.post(
            f'/api/purchase-orders/{po_id}/receive/',
            {'items': [
                {'po_item_id': items[0]['id'], 'quantity_received': '50.000'},
            ]},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'partial')

    def test_cannot_receive_cancelled_po(self):
        resp = self._create_po()
        po_id = resp.json()['id']
        items = resp.json()['items']
        self.client.post(f'/api/purchase-orders/{po_id}/cancel/')
        response = self.client.post(
            f'/api/purchase-orders/{po_id}/receive/',
            {'items': [
                {'po_item_id': items[0]['id'], 'quantity_received': '100.000'},
            ]},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_cancel_po(self):
        resp = self._create_po()
        po_id = resp.json()['id']
        response = self.client.post(f'/api/purchase-orders/{po_id}/cancel/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'cancelled')

    def test_audit_logs_created_on_receive(self):
        resp = self._create_po()
        po_id = resp.json()['id']
        items = resp.json()['items']
        self.client.post(f'/api/purchase-orders/{po_id}/submit/')
        self.client.post(
            f'/api/purchase-orders/{po_id}/receive/',
            {'items': [
                {'po_item_id': items[0]['id'], 'quantity_received': '100.000'},
            ]},
            content_type='application/json',
        )
        logs = StockAuditLog.objects.filter(movement_type='purchase')
        self.assertEqual(logs.count(), 1)
        log = logs.first()
        self.assertEqual(log.quantity_change, Decimal('100.000'))
        self.assertEqual(log.reference_type, 'PurchaseOrder')


class StockTransferAPITest(InventoryTestBase):
    def setUp(self):
        super().setUp()
        # Pre-populate OutletStock at source
        OutletStock.objects.create(
            outlet=self.outlet1, product=self.product,
            quantity=Decimal('500.000'),
        )

    def _create_transfer(self):
        self._auth(self.admin)
        return self.client.post('/api/stock-transfers/', {
            'from_outlet_id': self.outlet1.id,
            'to_outlet_id': self.outlet2.id,
            'items': [
                {'product_id': self.product.id, 'quantity': '100.000'},
            ],
        }, content_type='application/json')

    def test_create_transfer(self):
        response = self._create_transfer()
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data['transfer_number'].startswith('TRF-'))
        self.assertEqual(data['status'], 'pending')

    def test_dispatch_deducts_source(self):
        resp = self._create_transfer()
        transfer_id = resp.json()['id']
        response = self.client.post(f'/api/stock-transfers/{transfer_id}/dispatch/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'in_transit')

        # Source stock deducted
        os1 = OutletStock.objects.get(outlet=self.outlet1, product=self.product)
        self.assertEqual(os1.quantity, Decimal('400.000'))

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, Decimal('900.000'))

    def test_receive_transfer_adds_destination(self):
        resp = self._create_transfer()
        transfer_id = resp.json()['id']
        items = resp.json()['items']
        self.client.post(f'/api/stock-transfers/{transfer_id}/dispatch/')

        response = self.client.post(
            f'/api/stock-transfers/{transfer_id}/receive/',
            {'items': [
                {'transfer_item_id': items[0]['id'], 'quantity_received': '100.000'},
            ]},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'completed')

        # Destination stock added
        os2 = OutletStock.objects.get(outlet=self.outlet2, product=self.product)
        self.assertEqual(os2.quantity, Decimal('100.000'))

        # Product aggregate stock restored
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, Decimal('1000.000'))

    def test_insufficient_stock_on_dispatch(self):
        self._auth(self.admin)
        response = self.client.post('/api/stock-transfers/', {
            'from_outlet_id': self.outlet1.id,
            'to_outlet_id': self.outlet2.id,
            'items': [
                {'product_id': self.product.id, 'quantity': '999.000'},
            ],
        }, content_type='application/json')
        transfer_id = response.json()['id']
        response = self.client.post(f'/api/stock-transfers/{transfer_id}/dispatch/')
        self.assertEqual(response.status_code, 400)

    def test_cannot_dispatch_already_dispatched(self):
        resp = self._create_transfer()
        transfer_id = resp.json()['id']
        self.client.post(f'/api/stock-transfers/{transfer_id}/dispatch/')
        response = self.client.post(f'/api/stock-transfers/{transfer_id}/dispatch/')
        self.assertEqual(response.status_code, 400)

    def test_cancel_transfer(self):
        resp = self._create_transfer()
        transfer_id = resp.json()['id']
        response = self.client.post(f'/api/stock-transfers/{transfer_id}/cancel/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'cancelled')

    def test_cannot_cancel_dispatched(self):
        resp = self._create_transfer()
        transfer_id = resp.json()['id']
        self.client.post(f'/api/stock-transfers/{transfer_id}/dispatch/')
        response = self.client.post(f'/api/stock-transfers/{transfer_id}/cancel/')
        self.assertEqual(response.status_code, 400)

    def test_transfer_audit_logs(self):
        resp = self._create_transfer()
        transfer_id = resp.json()['id']
        items = resp.json()['items']
        self.client.post(f'/api/stock-transfers/{transfer_id}/dispatch/')
        self.client.post(
            f'/api/stock-transfers/{transfer_id}/receive/',
            {'items': [
                {'transfer_item_id': items[0]['id'], 'quantity_received': '100.000'},
            ]},
            content_type='application/json',
        )
        out_logs = StockAuditLog.objects.filter(movement_type='transfer_out')
        in_logs = StockAuditLog.objects.filter(movement_type='transfer_in')
        self.assertEqual(out_logs.count(), 1)
        self.assertEqual(in_logs.count(), 1)


class OutletStockAPITest(InventoryTestBase):
    def test_list_outlet_stock(self):
        OutletStock.objects.create(
            outlet=self.outlet1, product=self.product,
            quantity=Decimal('100.000'),
        )
        self._auth(self.admin)
        response = self.client.get('/api/outlet-stock/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)

    def test_low_stock(self):
        OutletStock.objects.create(
            outlet=self.outlet1, product=self.product,
            quantity=Decimal('50.000'),  # Below reorder_level of 100
        )
        self._auth(self.admin)
        response = self.client.get('/api/outlet-stock/low/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)

    def test_outlet_stock_auto_created_on_po_receive(self):
        supplier = Supplier.objects.create(name='Test Supplier')
        self._auth(self.admin)
        resp = self.client.post('/api/purchase-orders/', {
            'supplier_id': supplier.id,
            'outlet_id': self.outlet1.id,
            'items': [
                {
                    'product_id': self.product.id,
                    'quantity_ordered': '50.000',
                    'unit_cost': '3500.00',
                },
            ],
        }, content_type='application/json')
        po_id = resp.json()['id']
        items = resp.json()['items']
        self.client.post(f'/api/purchase-orders/{po_id}/submit/')
        self.client.post(
            f'/api/purchase-orders/{po_id}/receive/',
            {'items': [
                {'po_item_id': items[0]['id'], 'quantity_received': '50.000'},
            ]},
            content_type='application/json',
        )
        os = OutletStock.objects.get(outlet=self.outlet1, product=self.product)
        self.assertEqual(os.quantity, Decimal('50.000'))


class StockAuditLogAPITest(InventoryTestBase):
    def test_list_audit_logs(self):
        StockAuditLog.objects.create(
            product=self.product, outlet=self.outlet1,
            movement_type='adjustment', quantity_change=Decimal('10.000'),
            quantity_before=Decimal('100.000'), quantity_after=Decimal('110.000'),
        )
        self._auth(self.admin)
        response = self.client.get('/api/stock-audit-log/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)

    def test_filter_by_movement_type(self):
        StockAuditLog.objects.create(
            product=self.product, outlet=self.outlet1,
            movement_type='sale', quantity_change=Decimal('-10.000'),
            quantity_before=Decimal('100.000'), quantity_after=Decimal('90.000'),
        )
        StockAuditLog.objects.create(
            product=self.product, outlet=self.outlet1,
            movement_type='purchase', quantity_change=Decimal('50.000'),
            quantity_before=Decimal('90.000'), quantity_after=Decimal('140.000'),
        )
        self._auth(self.admin)
        response = self.client.get('/api/stock-audit-log/?movement_type=sale')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)


class CheckoutIntegrationTest(InventoryTestBase):
    """Tests that checkout creates OutletStock deductions and audit logs."""

    def setUp(self):
        super().setUp()
        from sales.models import Shift
        self.shift = Shift.objects.create(
            outlet=self.outlet1, user_id=self.cashier.id,
            opening_cash=Decimal('50000.00'),
        )

    def test_checkout_deducts_outlet_stock(self):
        self._auth(self.cashier)
        response = self.client.post('/api/checkout/', {
            'items': [{'product_id': self.product.id, 'quantity': '10.000'}],
            'payments': [{'payment_method': 'cash', 'amount': '100000.00'}],
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)

        # OutletStock should be auto-created with negative balance
        os = OutletStock.objects.get(outlet=self.outlet1, product=self.product)
        self.assertEqual(os.quantity, Decimal('-10.000'))

        # Audit log created
        log = StockAuditLog.objects.filter(movement_type='sale').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.quantity_change, Decimal('-10.000'))

    def test_void_restores_outlet_stock(self):
        self._auth(self.cashier)
        resp = self.client.post('/api/checkout/', {
            'items': [{'product_id': self.product.id, 'quantity': '10.000'}],
            'payments': [{'payment_method': 'cash', 'amount': '100000.00'}],
        }, content_type='application/json')
        sale_id = resp.json()['id']

        self._auth(self.admin)
        response = self.client.post(f'/api/sales/{sale_id}/void/')
        self.assertEqual(response.status_code, 200)

        os = OutletStock.objects.get(outlet=self.outlet1, product=self.product)
        self.assertEqual(os.quantity, Decimal('0.000'))

        void_log = StockAuditLog.objects.filter(movement_type='void').first()
        self.assertIsNotNone(void_log)
        self.assertEqual(void_log.quantity_change, Decimal('10.000'))
