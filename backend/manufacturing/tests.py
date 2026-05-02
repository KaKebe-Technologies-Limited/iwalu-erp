import json
from decimal import Decimal
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from django.contrib.auth import get_user_model
from products.models import Product, Category
from outlets.models import Outlet
from inventory.models import OutletStock, StockAuditLog
from .models import BillOfMaterials, BOMItem, ProductionOrder, WorkInProgress, ProductionOrderItem

User = get_user_model()


class ManufacturingTestCase(TenantTestCase):
    def setUp(self):
        super().setUp()
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
        
        self.outlet = Outlet.objects.create(name="Main Bakery", address="Kampala", outlet_type="cafe")
        self.category = Category.objects.create(name="Bakery", business_unit="cafe")
        
        # Raw materials
        self.flour = Product.objects.create(
            name="Wheat Flour", sku="RM-001", category=self.category,
            cost_price=Decimal('4000'), selling_price=Decimal('5000'),
            unit="kg", is_active=True
        )
        self.water = Product.objects.create(
            name="Water", sku="RM-002", category=self.category,
            cost_price=Decimal('500'), selling_price=Decimal('1000'),
            unit="litre", is_active=True
        )
        
        # Finished product
        self.bread = Product.objects.create(
            name="Bread Loaf", sku="FP-001", category=self.category,
            cost_price=Decimal('0'), selling_price=Decimal('2000'),
            unit="piece", is_active=True
        )
        
        # Setup initial stock
        OutletStock.objects.create(outlet=self.outlet, product=self.flour, quantity=Decimal('100'))
        OutletStock.objects.create(outlet=self.outlet, product=self.water, quantity=Decimal('100'))

    def _auth(self, user):
        response = self.client.post('/api/auth/login/', {
            'email': user.email, 'password': 'testpass123',
        })
        token = response.json()['access']
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {token}'

    def test_create_bom_with_items(self):
        self._auth(self.admin)
        data = {
            "name": "Standard Bread BOM",
            "finished_product_id": self.bread.id,
            "output_quantity": "10.000",
            "output_unit": "piece",
            "version": "1.0",
            "items": [
                {"raw_material_id": self.flour.id, "quantity_required": "2.500", "unit": "kg", "waste_factor_pct": "5.00"},
                {"raw_material_id": self.water.id, "quantity_required": "1.500", "unit": "litre", "waste_factor_pct": "0.00"}
            ]
        }
        response = self.client.post('/api/manufacturing/boms/', data, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        
        bom = BillOfMaterials.objects.get(id=response.json()['id'])
        self.assertEqual(bom.items.count(), 2)
        # Flour effective quantity: 2.5 * 1.05 = 2.625
        # Water effective quantity: 1.5 * 1.00 = 1.500
        # Total batch cost: (2.625 * 4000) + (1.5 * 500) = 10500 + 750 = 11250
        # Unit cost: 11250 / 10 = 1125
        self.assertEqual(bom.unit_cost, Decimal('1125.00'))

    def test_cost_endpoint_requires_manager(self):
        bom = BillOfMaterials.objects.create(
            name="Bread BOM", finished_product=self.bread,
            output_quantity=Decimal('10'), output_unit="piece",
            created_by_id=self.admin.id
        )
        
        self._auth(self.cashier)
        response = self.client.get(f'/api/manufacturing/boms/{bom.id}/cost/')
        self.assertEqual(response.status_code, 403)
        
        self._auth(self.manager)
        response = self.client.get(f'/api/manufacturing/boms/{bom.id}/cost/')
        self.assertEqual(response.status_code, 200)

    def test_complete_order_stock_movements(self):
        self._auth(self.admin)
        # Create BOM
        bom = BillOfMaterials.objects.create(
            name="Bread BOM", finished_product=self.bread,
            output_quantity=Decimal('10'), output_unit="piece",
            created_by_id=self.admin.id
        )
        BOMItem.objects.create(bom=bom, raw_material=self.flour, quantity_required=Decimal('2'), unit="kg", waste_factor_pct=Decimal('0'))
        
        # Create Order
        response = self.client.post('/api/manufacturing/orders/', {
            "bom_id": bom.id,
            "quantity_to_produce": "20.000",
            "outlet_id": self.outlet.id
        }, content_type='application/json')
        order_id = response.json()['id']
        
        # Start Order
        self.client.post(f'/api/manufacturing/orders/{order_id}/start/')
        
        # Initial stocks
        flour_stock = OutletStock.objects.get(outlet=self.outlet, product=self.flour).quantity
        bread_stock = OutletStock.objects.filter(outlet=self.outlet, product=self.bread).first()
        initial_bread_qty = bread_stock.quantity if bread_stock else Decimal('0')
        
        # Complete Order
        response = self.client.post(f'/api/manufacturing/orders/{order_id}/complete/', {
            "quantity_produced": "20.000"
        }, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        # Verify stocks
        # 20 to produce / 10 output = 2 batches
        # 2 kg flour per batch * 2 batches = 4 kg flour deducted
        self.assertEqual(
            OutletStock.objects.get(outlet=self.outlet, product=self.flour).quantity,
            flour_stock - Decimal('4')
        )
        # 20 loaves bread added
        self.assertEqual(
            OutletStock.objects.get(outlet=self.outlet, product=self.bread).quantity,
            initial_bread_qty + Decimal('20')
        )
        
        # Verify audit logs
        self.assertEqual(StockAuditLog.objects.filter(reference_type='manufacturing_order', reference_id=order_id).count(), 2)

    def test_complete_order_insufficient_stock(self):
        self._auth(self.admin)
        bom = BillOfMaterials.objects.create(
            name="Bread BOM", finished_product=self.bread,
            output_quantity=Decimal('10'), output_unit="piece",
            created_by_id=self.admin.id
        )
        BOMItem.objects.create(bom=bom, raw_material=self.flour, quantity_required=Decimal('100'), unit="kg")
        
        response = self.client.post('/api/manufacturing/orders/', {
            "bom_id": bom.id,
            "quantity_to_produce": "20.000",
            "outlet_id": self.outlet.id
        }, content_type='application/json')
        order_id = response.json()['id']
        self.client.post(f'/api/manufacturing/orders/{order_id}/start/')
        
        # Try complete - needs 200kg, only has 100kg
        response = self.client.post(f'/api/manufacturing/orders/{order_id}/complete/')
        self.assertEqual(response.status_code, 400)
        self.assertIn('shortages', response.json())

    def test_update_bom_costs_command(self):
        bom = BillOfMaterials.objects.create(
            name="Bread BOM", finished_product=self.bread,
            output_quantity=Decimal('1'), output_unit="piece",
            created_by_id=self.admin.id,
            unit_cost=Decimal('4000') # Old cost based on 1kg flour
        )
        BOMItem.objects.create(bom=bom, raw_material=self.flour, quantity_required=Decimal('1'), unit="kg")
        
        # Change flour price
        self.flour.cost_price = Decimal('5000')
        self.flour.save()
        
        # Run command
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command('update_bom_costs', stdout=out)
        
        bom.refresh_from_db()
        self.assertEqual(bom.unit_cost, Decimal('5000.00'))

    def test_inactive_bom_cannot_create_order(self):
        self._auth(self.admin)
        bom = BillOfMaterials.objects.create(
            name="Inactive BOM", finished_product=self.bread,
            output_quantity=Decimal('10'), is_active=False,
            created_by_id=self.admin.id
        )
        
        response = self.client.post('/api/manufacturing/orders/', {
            "bom_id": bom.id,
            "quantity_to_produce": "10.000",
            "outlet_id": self.outlet.id
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('bom_id', response.json())
