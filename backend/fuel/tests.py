from decimal import Decimal
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from django.contrib.auth import get_user_model

from outlets.models import Outlet
from products.models import Category, Product
from inventory.models import Supplier, OutletStock, StockAuditLog
from sales.models import Shift
from .models import (
    Pump, Tank, TankReading, PumpReading,
    FuelDelivery, FuelReconciliation,
)

User = get_user_model()


class FuelTestBase(TenantTestCase):
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
        self.outlet = Outlet.objects.create(
            name='Main Station', outlet_type='fuel_station',
        )
        self.category = Category.objects.create(
            name='Fuels', business_unit='fuel',
        )
        self.petrol = Product.objects.create(
            name='Petrol', sku='PET-001', category=self.category,
            cost_price=Decimal('3500.00'), selling_price=Decimal('4500.00'),
            tax_rate=Decimal('18.00'), stock_quantity=Decimal('1000.000'),
            reorder_level=Decimal('100.000'), unit='litre',
        )
        self.diesel = Product.objects.create(
            name='Diesel', sku='DSL-001', category=self.category,
            cost_price=Decimal('3200.00'), selling_price=Decimal('4200.00'),
            tax_rate=Decimal('18.00'), stock_quantity=Decimal('500.000'),
            reorder_level=Decimal('50.000'), unit='litre',
        )
        self.supplier = Supplier.objects.create(
            name='Total Energies',
            contact_person='John Doe',
            email='john@total.com',
            phone='+256700000000',
        )

    def _auth(self, user):
        response = self.client.post('/api/auth/login/', {
            'email': user.email, 'password': 'testpass123',
        })
        token = response.json()['access']
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {token}'

    def _create_pump(self, **kwargs):
        defaults = {
            'outlet': self.outlet,
            'product': self.petrol,
            'pump_number': 1,
            'name': 'Pump 1 - Petrol',
        }
        defaults.update(kwargs)
        return Pump.objects.create(**defaults)

    def _create_tank(self, **kwargs):
        defaults = {
            'outlet': self.outlet,
            'product': self.petrol,
            'name': 'Underground Tank 1',
            'capacity': Decimal('10000.000'),
            'current_level': Decimal('5000.000'),
            'reorder_level': Decimal('1000.000'),
        }
        defaults.update(kwargs)
        return Tank.objects.create(**defaults)

    def _open_shift(self, user):
        return Shift.objects.create(
            outlet=self.outlet,
            user_id=user.pk,
            opened_at=timezone.now(),
            opening_cash=Decimal('0.00'),
        )


# ---------- Pump Tests ----------

class PumpAPITest(FuelTestBase):
    def test_admin_can_create_pump(self):
        self._auth(self.admin)
        response = self.client.post('/api/fuel/pumps/', {
            'outlet': self.outlet.pk,
            'product': self.petrol.pk,
            'pump_number': 1,
            'name': 'Pump 1 - Petrol',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['pump_number'], 1)

    def test_cashier_cannot_create_pump(self):
        self._auth(self.cashier)
        response = self.client.post('/api/fuel/pumps/', {
            'outlet': self.outlet.pk,
            'product': self.petrol.pk,
            'pump_number': 1,
        }, content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_list_pumps(self):
        self._create_pump()
        self._auth(self.cashier)
        response = self.client.get('/api/fuel/pumps/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)

    def test_filter_pumps_by_outlet(self):
        self._create_pump()
        outlet2 = Outlet.objects.create(name='Branch', outlet_type='fuel_station')
        self._create_pump(outlet=outlet2, pump_number=2, name='Pump 2')
        self._auth(self.cashier)
        response = self.client.get(f'/api/fuel/pumps/?outlet={self.outlet.pk}')
        self.assertEqual(response.json()['count'], 1)

    def test_activate_pump(self):
        pump = self._create_pump(status='inactive')
        self._auth(self.admin)
        response = self.client.post(f'/api/fuel/pumps/{pump.pk}/activate/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'active')

    def test_deactivate_pump(self):
        pump = self._create_pump(status='active')
        self._auth(self.admin)
        response = self.client.post(f'/api/fuel/pumps/{pump.pk}/deactivate/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'inactive')

    def test_set_maintenance(self):
        pump = self._create_pump(status='active')
        self._auth(self.admin)
        response = self.client.post(f'/api/fuel/pumps/{pump.pk}/set-maintenance/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'maintenance')

    def test_invalid_status_transition(self):
        pump = self._create_pump(status='inactive')
        self._auth(self.admin)
        response = self.client.post(f'/api/fuel/pumps/{pump.pk}/deactivate/')
        self.assertEqual(response.status_code, 400)

    def test_duplicate_pump_number_same_outlet(self):
        self._create_pump(pump_number=1)
        self._auth(self.admin)
        response = self.client.post('/api/fuel/pumps/', {
            'outlet': self.outlet.pk,
            'product': self.diesel.pk,
            'pump_number': 1,
        }, content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_activate_from_maintenance(self):
        pump = self._create_pump(status='maintenance')
        self._auth(self.admin)
        response = self.client.post(f'/api/fuel/pumps/{pump.pk}/activate/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'active')


# ---------- Tank Tests ----------

class TankAPITest(FuelTestBase):
    def test_admin_can_create_tank(self):
        self._auth(self.admin)
        response = self.client.post('/api/fuel/tanks/', {
            'outlet': self.outlet.pk,
            'product': self.petrol.pk,
            'name': 'Tank 1',
            'capacity': '10000.000',
            'reorder_level': '1000.000',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['current_level'], '0.000')

    def test_record_reading_updates_level(self):
        tank = self._create_tank(current_level=Decimal('5000.000'))
        self._auth(self.attendant)
        response = self.client.post(
            f'/api/fuel/tanks/{tank.pk}/record-reading/',
            {'reading_level': '4500.000', 'reading_type': 'manual'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        tank.refresh_from_db()
        self.assertEqual(tank.current_level, Decimal('4500.000'))

    def test_reading_exceeds_capacity(self):
        tank = self._create_tank(capacity=Decimal('10000.000'))
        self._auth(self.attendant)
        response = self.client.post(
            f'/api/fuel/tanks/{tank.pk}/record-reading/',
            {'reading_level': '15000.000', 'reading_type': 'manual'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_negative_reading(self):
        tank = self._create_tank()
        self._auth(self.attendant)
        response = self.client.post(
            f'/api/fuel/tanks/{tank.pk}/record-reading/',
            {'reading_level': '-100', 'reading_type': 'manual'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_list_readings(self):
        tank = self._create_tank()
        TankReading.objects.create(
            tank=tank, reading_level=Decimal('5000.000'),
            reading_type='manual', recorded_by=self.admin.pk,
            reading_at=timezone.now(),
        )
        self._auth(self.cashier)
        response = self.client.get(f'/api/fuel/tanks/{tank.pk}/readings/')
        self.assertEqual(response.status_code, 200)

    def test_low_levels_action(self):
        self._create_tank(
            name='Low Tank',
            current_level=Decimal('500.000'),
            reorder_level=Decimal('1000.000'),
        )
        self._create_tank(
            name='OK Tank',
            product=self.diesel,
            current_level=Decimal('5000.000'),
            reorder_level=Decimal('1000.000'),
        )
        self._auth(self.admin)
        response = self.client.get('/api/fuel/tanks/low-levels/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]['name'], 'Low Tank')

    def test_fill_percentage(self):
        tank = self._create_tank(
            capacity=Decimal('10000.000'),
            current_level=Decimal('7500.000'),
        )
        self._auth(self.cashier)
        response = self.client.get(f'/api/fuel/tanks/{tank.pk}/')
        self.assertEqual(response.json()['fill_percentage'], 75.0)


# ---------- Fuel Delivery Tests ----------

class FuelDeliveryAPITest(FuelTestBase):
    def test_create_delivery_updates_tank_level(self):
        tank = self._create_tank(current_level=Decimal('5000.000'))
        self._auth(self.admin)
        response = self.client.post('/api/fuel/deliveries/', {
            'tank_id': tank.pk,
            'supplier_id': self.supplier.pk,
            'delivery_date': timezone.now().isoformat(),
            'volume_received': '2000.000',
            'unit_cost': '3500.00',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        tank.refresh_from_db()
        self.assertEqual(tank.current_level, Decimal('7000.000'))

    def test_delivery_overfill_rejected(self):
        tank = self._create_tank(
            capacity=Decimal('10000.000'),
            current_level=Decimal('9000.000'),
        )
        self._auth(self.admin)
        response = self.client.post('/api/fuel/deliveries/', {
            'tank_id': tank.pk,
            'supplier_id': self.supplier.pk,
            'delivery_date': timezone.now().isoformat(),
            'volume_received': '2000.000',
            'unit_cost': '3500.00',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_delivery_creates_audit_log(self):
        tank = self._create_tank(current_level=Decimal('5000.000'))
        self._auth(self.admin)
        self.client.post('/api/fuel/deliveries/', {
            'tank_id': tank.pk,
            'supplier_id': self.supplier.pk,
            'delivery_date': timezone.now().isoformat(),
            'volume_received': '1000.000',
            'unit_cost': '3500.00',
        }, content_type='application/json')
        self.assertTrue(
            StockAuditLog.objects.filter(
                reference_type='FuelDelivery',
                movement_type='purchase',
            ).exists()
        )

    def test_delivery_updates_outlet_stock(self):
        tank = self._create_tank(current_level=Decimal('5000.000'))
        self._auth(self.admin)
        self.client.post('/api/fuel/deliveries/', {
            'tank_id': tank.pk,
            'supplier_id': self.supplier.pk,
            'delivery_date': timezone.now().isoformat(),
            'volume_received': '1000.000',
            'unit_cost': '3500.00',
        }, content_type='application/json')
        stock = OutletStock.objects.get(outlet=self.outlet, product=self.petrol)
        self.assertEqual(stock.quantity, Decimal('1000.000'))

    def test_delivery_captures_tank_levels(self):
        tank = self._create_tank(current_level=Decimal('5000.000'))
        self._auth(self.admin)
        response = self.client.post('/api/fuel/deliveries/', {
            'tank_id': tank.pk,
            'supplier_id': self.supplier.pk,
            'delivery_date': timezone.now().isoformat(),
            'volume_received': '2000.000',
            'unit_cost': '3500.00',
        }, content_type='application/json')
        data = response.json()
        self.assertEqual(data['tank_level_before'], '5000.000')
        self.assertEqual(data['tank_level_after'], '7000.000')

    def test_cashier_cannot_create_delivery(self):
        tank = self._create_tank()
        self._auth(self.cashier)
        response = self.client.post('/api/fuel/deliveries/', {
            'tank_id': tank.pk,
            'supplier_id': self.supplier.pk,
            'delivery_date': timezone.now().isoformat(),
            'volume_received': '1000.000',
            'unit_cost': '3500.00',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_delivery_total_cost_computed(self):
        tank = self._create_tank(current_level=Decimal('5000.000'))
        self._auth(self.admin)
        response = self.client.post('/api/fuel/deliveries/', {
            'tank_id': tank.pk,
            'supplier_id': self.supplier.pk,
            'delivery_date': timezone.now().isoformat(),
            'volume_received': '2000.000',
            'unit_cost': '3500.00',
        }, content_type='application/json')
        self.assertEqual(response.json()['total_cost'], '7000000.00')


# ---------- Pump Reading Tests ----------

class PumpReadingAPITest(FuelTestBase):
    def test_create_pump_reading_with_open_shift(self):
        pump = self._create_pump()
        shift = self._open_shift(self.cashier)
        self._auth(self.cashier)
        response = self.client.post('/api/fuel/pump-readings/', {
            'pump_id': pump.pk,
            'shift_id': shift.pk,
            'opening_reading': '10000.000',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.json()['closing_reading'])

    def test_cannot_create_for_closed_shift(self):
        pump = self._create_pump()
        shift = self._open_shift(self.cashier)
        shift.closed_at = timezone.now()
        shift.save(update_fields=['closed_at'])
        self._auth(self.cashier)
        response = self.client.post('/api/fuel/pump-readings/', {
            'pump_id': pump.pk,
            'shift_id': shift.pk,
            'opening_reading': '10000.000',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_close_pump_reading(self):
        pump = self._create_pump()
        shift = self._open_shift(self.cashier)
        reading = PumpReading.objects.create(
            pump=pump, shift=shift,
            opening_reading=Decimal('10000.000'),
            recorded_by=self.cashier.pk,
        )
        self._auth(self.cashier)
        response = self.client.post(
            f'/api/fuel/pump-readings/{reading.pk}/close/',
            {'closing_reading': '10500.000'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['closing_reading'], '10500.000')
        self.assertEqual(response.json()['volume_dispensed'], '500.000')

    def test_closing_less_than_opening(self):
        pump = self._create_pump()
        shift = self._open_shift(self.cashier)
        reading = PumpReading.objects.create(
            pump=pump, shift=shift,
            opening_reading=Decimal('10000.000'),
            recorded_by=self.cashier.pk,
        )
        self._auth(self.cashier)
        response = self.client.post(
            f'/api/fuel/pump-readings/{reading.pk}/close/',
            {'closing_reading': '9000.000'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_duplicate_pump_shift_reading(self):
        pump = self._create_pump()
        shift = self._open_shift(self.cashier)
        PumpReading.objects.create(
            pump=pump, shift=shift,
            opening_reading=Decimal('10000.000'),
            recorded_by=self.cashier.pk,
        )
        self._auth(self.cashier)
        response = self.client.post('/api/fuel/pump-readings/', {
            'pump_id': pump.pk,
            'shift_id': shift.pk,
            'opening_reading': '10500.000',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_inactive_pump_rejected(self):
        pump = self._create_pump(status='inactive')
        shift = self._open_shift(self.cashier)
        self._auth(self.cashier)
        response = self.client.post('/api/fuel/pump-readings/', {
            'pump_id': pump.pk,
            'shift_id': shift.pk,
            'opening_reading': '10000.000',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_volume_dispensed_null_when_open(self):
        pump = self._create_pump()
        shift = self._open_shift(self.cashier)
        reading = PumpReading.objects.create(
            pump=pump, shift=shift,
            opening_reading=Decimal('10000.000'),
            recorded_by=self.cashier.pk,
        )
        self.assertIsNone(reading.volume_dispensed)


# ---------- Fuel Reconciliation Tests ----------

class FuelReconciliationAPITest(FuelTestBase):
    def test_calculate_reconciliation(self):
        tank = self._create_tank(current_level=Decimal('5000.000'))
        today = timezone.now().date()
        # Create a reading for the day
        TankReading.objects.create(
            tank=tank, reading_level=Decimal('5000.000'),
            reading_type='manual', recorded_by=self.admin.pk,
            reading_at=timezone.now(),
        )
        self._auth(self.admin)
        response = self.client.post('/api/fuel/reconciliations/calculate/', {
            'tank_id': tank.pk,
            'date': today.isoformat(),
            'closing_stock': '4800.000',
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['closing_stock'], '4800.000')
        self.assertIn(data['variance_type'], ['gain', 'loss', 'within_tolerance'])

    def test_reconciliation_loss_detected(self):
        tank = self._create_tank(current_level=Decimal('5000.000'))
        today = timezone.now().date()
        TankReading.objects.create(
            tank=tank, reading_level=Decimal('5000.000'),
            reading_type='manual', recorded_by=self.admin.pk,
            reading_at=timezone.now(),
        )
        self._auth(self.admin)
        response = self.client.post('/api/fuel/reconciliations/calculate/', {
            'tank_id': tank.pk,
            'date': today.isoformat(),
            'closing_stock': '4500.000',  # 500L loss, > 0.5% tolerance
        }, content_type='application/json')
        self.assertEqual(response.json()['variance_type'], 'loss')

    def test_reconciliation_within_tolerance(self):
        tank = self._create_tank(current_level=Decimal('5000.000'))
        today = timezone.now().date()
        TankReading.objects.create(
            tank=tank, reading_level=Decimal('5000.000'),
            reading_type='manual', recorded_by=self.admin.pk,
            reading_at=timezone.now(),
        )
        self._auth(self.admin)
        response = self.client.post('/api/fuel/reconciliations/calculate/', {
            'tank_id': tank.pk,
            'date': today.isoformat(),
            'closing_stock': '4990.000',  # 10L loss on 5000L = 0.2%
        }, content_type='application/json')
        self.assertEqual(response.json()['variance_type'], 'within_tolerance')

    def test_confirm_reconciliation(self):
        tank = self._create_tank()
        recon = FuelReconciliation.objects.create(
            date=timezone.now().date(), outlet=self.outlet, tank=tank,
            opening_stock=Decimal('5000.000'), closing_stock=Decimal('4900.000'),
            total_received=Decimal('0'), total_dispensed=Decimal('100.000'),
            expected_closing=Decimal('4900.000'), variance=Decimal('0'),
            variance_percentage=Decimal('0'), variance_type='within_tolerance',
            reconciled_by=self.admin.pk,
        )
        self._auth(self.admin)
        response = self.client.post(f'/api/fuel/reconciliations/{recon.pk}/confirm/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'confirmed')

    def test_cannot_confirm_already_confirmed(self):
        tank = self._create_tank()
        recon = FuelReconciliation.objects.create(
            date=timezone.now().date(), outlet=self.outlet, tank=tank,
            opening_stock=Decimal('5000.000'), closing_stock=Decimal('4900.000'),
            total_received=Decimal('0'), total_dispensed=Decimal('100.000'),
            expected_closing=Decimal('4900.000'), variance=Decimal('0'),
            variance_percentage=Decimal('0'), variance_type='within_tolerance',
            status='confirmed', reconciled_by=self.admin.pk,
        )
        self._auth(self.admin)
        response = self.client.post(f'/api/fuel/reconciliations/{recon.pk}/confirm/')
        self.assertEqual(response.status_code, 400)

    def test_variance_alerts_endpoint(self):
        tank = self._create_tank()
        FuelReconciliation.objects.create(
            date=timezone.now().date(), outlet=self.outlet, tank=tank,
            opening_stock=Decimal('5000.000'), closing_stock=Decimal('4000.000'),
            total_received=Decimal('0'), total_dispensed=Decimal('0'),
            expected_closing=Decimal('5000.000'), variance=Decimal('-1000.000'),
            variance_percentage=Decimal('-20.00'), variance_type='loss',
            reconciled_by=self.admin.pk,
        )
        self._auth(self.admin)
        response = self.client.get('/api/fuel/reconciliations/variance-alerts/')
        self.assertEqual(response.status_code, 200)
        results = response.json()['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['variance_type'], 'loss')

    def test_cashier_cannot_calculate(self):
        tank = self._create_tank()
        self._auth(self.cashier)
        response = self.client.post('/api/fuel/reconciliations/calculate/', {
            'tank_id': tank.pk,
            'date': timezone.now().date().isoformat(),
        }, content_type='application/json')
        self.assertEqual(response.status_code, 403)


# ---------- Report Tests ----------

class FuelReportTest(FuelTestBase):
    def test_daily_pump_report(self):
        pump = self._create_pump()
        shift = self._open_shift(self.cashier)
        PumpReading.objects.create(
            pump=pump, shift=shift,
            opening_reading=Decimal('10000.000'),
            closing_reading=Decimal('10500.000'),
            recorded_by=self.cashier.pk,
        )
        self._auth(self.admin)
        today = timezone.now().date().isoformat()
        response = self.client.get(f'/api/fuel/reports/daily-pump/?date={today}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['pumps']), 1)

    def test_daily_pump_report_requires_date(self):
        self._auth(self.admin)
        response = self.client.get('/api/fuel/reports/daily-pump/')
        self.assertEqual(response.status_code, 400)

    def test_variance_report(self):
        tank = self._create_tank()
        today = timezone.now().date()
        FuelReconciliation.objects.create(
            date=today, outlet=self.outlet, tank=tank,
            opening_stock=Decimal('5000.000'), closing_stock=Decimal('4000.000'),
            total_received=Decimal('0'), total_dispensed=Decimal('0'),
            expected_closing=Decimal('5000.000'), variance=Decimal('-1000.000'),
            variance_percentage=Decimal('-20.00'), variance_type='loss',
            reconciled_by=self.admin.pk,
        )
        self._auth(self.admin)
        response = self.client.get(
            f'/api/fuel/reports/variance/?date_from={today}&date_to={today}',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['summary']['loss_count'], 1)

    def test_tank_levels_summary(self):
        self._create_tank(name='Tank A')
        self._create_tank(name='Tank B', product=self.diesel)
        self._auth(self.cashier)
        response = self.client.get('/api/fuel/reports/tank-levels/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)
