from decimal import Decimal
from datetime import date
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
from django.contrib.auth import get_user_model
from rest_framework import status
from .models import AssetCategory, Asset, AssetAssignment, MaintenanceLog, AssetDisposal

User = get_user_model()

class AssetsTest(TenantTestCase):
    def setUp(self):
        super().setUp()
        self.tenant_client = TenantClient(self.tenant)
        self.admin = User.objects.create_user(
            email='admin@test.com', username='admin',
            password='testpass123', role='admin',
        )
        self.tenant_client.force_login(self.admin)
        
        self.category = AssetCategory.objects.create(
            name="Fuel Pumps",
            default_useful_life_years=10,
            default_depreciation_method=AssetCategory.DepreciationMethod.STRAIGHT_LINE
        )

    def test_create_category(self):
        cat = AssetCategory.objects.create(name="Vehicles", default_useful_life_years=5)
        self.assertEqual(cat.name, "Vehicles")
        self.assertEqual(cat.default_useful_life_years, 5)

    def test_create_asset_calculates_book_value(self):
        asset = Asset.objects.create(
            asset_code="PUMP-001",
            name="Premium Pump 1",
            category=self.category,
            acquisition_date=date(2024, 1, 1),
            cost=Decimal('12000000.00'),
            useful_life_years=10
        )
        self.assertEqual(asset.book_value, Decimal('12000000.00'))
        
        asset.accumulated_depreciation = Decimal('2000000.00')
        asset.save()
        self.assertEqual(asset.book_value, Decimal('10000000.00'))

    def test_straight_line_depreciation_monthly(self):
        # (12,000,000 - 0) / (10 * 12) = 100,000 per month
        asset = Asset.objects.create(
            asset_code="PUMP-001",
            name="Premium Pump 1",
            category=self.category,
            acquisition_date=date(2024, 1, 1),
            cost=Decimal('12000000.00'),
            useful_life_years=10,
            depreciation_method=AssetCategory.DepreciationMethod.STRAIGHT_LINE,
            residual_value=Decimal('0')
        )
        self.assertEqual(asset.calculate_monthly_depreciation(), Decimal('100000.00'))

    def test_reducing_balance_depreciation_monthly(self):
        # 12,000,000 * 0.20 / 12 = 200,000 per month
        asset = Asset.objects.create(
            asset_code="PUMP-002",
            name="Diesel Pump 2",
            category=self.category,
            acquisition_date=date(2024, 1, 1),
            cost=Decimal('12000000.00'),
            useful_life_years=10,
            depreciation_method=AssetCategory.DepreciationMethod.REDUCING_BALANCE,
            depreciation_rate_pct=Decimal('20.00')
        )
        self.assertEqual(asset.calculate_monthly_depreciation(), Decimal('200000.00'))

    def test_is_fully_depreciated(self):
        asset = Asset.objects.create(
            asset_code="PUMP-003",
            name="Old Pump",
            category=self.category,
            acquisition_date=date(2010, 1, 1),
            cost=Decimal('1000000.00'),
            useful_life_years=5,
            accumulated_depreciation=Decimal('1000000.00')
        )
        self.assertTrue(asset.is_fully_depreciated)
        self.assertEqual(asset.calculate_monthly_depreciation(), Decimal('0'))

    def test_asset_assignment_history(self):
        asset = Asset.objects.create(
            asset_code="VEH-001", name="Manager Van",
            category=self.category, acquisition_date=date(2024, 1, 1),
            cost=Decimal('50000000.00'), useful_life_years=5
        )
        
        # Initial assignment
        assignment1 = AssetAssignment.objects.create(
            asset=asset, assigned_to_id=1, assigned_to_type='employee',
            assigned_date=date(2024, 1, 1), is_current=True
        )
        self.assertEqual(asset.assignments.count(), 1)
        
        # New assignment
        assignment1.is_current = False
        assignment1.returned_date = date(2024, 6, 30)
        assignment1.save()
        
        AssetAssignment.objects.create(
            asset=asset, assigned_to_id=2, assigned_to_type='employee',
            assigned_date=date(2024, 7, 1), is_current=True
        )
        
        self.assertEqual(asset.assignments.count(), 2)
        self.assertEqual(asset.assignments.filter(is_current=True).count(), 1)

    def test_maintenance_log(self):
        asset = Asset.objects.create(
            asset_code="PUMP-001", name="Pump 1",
            category=self.category, acquisition_date=date(2024, 1, 1),
            cost=Decimal('10000000.00'), useful_life_years=10
        )
        
        log = MaintenanceLog.objects.create(
            asset=asset,
            maintenance_type=MaintenanceLog.MaintenanceType.REPAIR,
            performed_date=date(2024, 5, 1),
            cost=Decimal('500000.00'),
            description="Replaced nozzle"
        )
        self.assertEqual(asset.maintenance_logs.count(), 1)
        self.assertEqual(asset.maintenance_logs.first().cost, Decimal('500000.00'))

    def test_asset_disposal(self):
        asset = Asset.objects.create(
            asset_code="PUMP-DISP", name="To be sold",
            category=self.category, acquisition_date=date(2024, 1, 1),
            cost=Decimal('10000000.00'), useful_life_years=10,
            accumulated_depreciation=Decimal('2000000.00')
        )
        # book_value = 8,000,000
        
        disposal = AssetDisposal.objects.create(
            asset=asset,
            disposal_date=date(2024, 6, 1),
            disposal_method=AssetDisposal.DisposalMethod.SALE,
            proceeds=Decimal('7000000.00')
        )
        
        self.assertEqual(disposal.book_value_at_disposal, Decimal('8000000.00'))
        self.assertEqual(disposal.gain_or_loss, Decimal('-1000000.00')) # Loss of 1M
        
        asset.refresh_from_db()
        self.assertEqual(asset.status, Asset.Status.DISPOSED)

    def test_api_list_assets(self):
        Asset.objects.create(
            asset_code="P-1", name="Pump 1", category=self.category,
            acquisition_date=date(2024, 1, 1), cost=Decimal('1000.00'),
            useful_life_years=10
        )
        response = self.tenant_client.get('/api/assets/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)

    def test_api_create_asset(self):
        data = {
            "asset_code": "P-2",
            "name": "Pump 2",
            "category_id": self.category.id,
            "acquisition_date": "2024-01-01",
            "cost": "2000000.00",
            "useful_life_years": 5,
            "location": "Main Station"
        }
        response = self.tenant_client.post('/api/assets/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Asset.objects.filter(asset_code="P-2").count(), 1)

    def test_api_assign_asset(self):
        asset = Asset.objects.create(
            asset_code="P-3", name="Pump 3", category=self.category,
            acquisition_date=date(2024, 1, 1), cost=Decimal('1000.00'),
            useful_life_years=10
        )
        data = {"assigned_to_id": 10, "assigned_to_type": "employee"}
        response = self.tenant_client.post(f'/api/assets/{asset.id}/assign/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        asset.refresh_from_db()
        self.assertEqual(asset.assigned_to_id, 10)
        self.assertEqual(asset.assignments.filter(is_current=True).count(), 1)
