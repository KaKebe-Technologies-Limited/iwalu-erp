# Phase 7d Implementation Plan: Asset Management

**Backend only** (tenant-scoped, new `assets` app)  
**Estimated scope**: 4 models, 8 endpoints, ~35 tests, optional finance integration  
**New apps**: `assets` (tenant-scoped)  
**Tenant-scoped**: Yes

---

## Overview

Implements fixed asset tracking for businesses:
1. **Asset registration**: Categorization, cost, acquisition date, location, responsible staff
2. **Assignment lifecycle**: Assignment to staff/departments, change tracking
3. **Maintenance logs**: Service/repair history with costs
4. **Depreciation calculation**: Multiple methods (straight-line, reducing balance, units of production)
5. **Disposal tracking**: Sale/scrap records with gain/loss calculation
6. **Finance integration** (optional): Auto-create depreciation journal entries to GL

Assets apply to fuel stations (pumps, tanks, signage), offices (furniture, equipment), vehicles, etc.

---

## Models

### `AssetCategory` (in `assets/models.py`)

```python
class AssetCategory(models.Model):
    """
    Asset type classification. Admin-managed.
    """
    class DepreciationMethod(models.TextChoices):
        STRAIGHT_LINE = 'straight_line', 'Straight-Line'
        REDUCING_BALANCE = 'reducing_balance', 'Reducing Balance (Declining Balance)'
        UNITS = 'units', 'Units of Production'
        NO_DEPRECIATION = 'none', 'No Depreciation'

    name = models.CharField(max_length=100, unique=True, help_text='e.g., "Fuel Pumps", "Office Furniture"')
    description = models.TextField(blank=True)
    
    # Default useful life (years) for new assets in this category
    default_useful_life_years = models.PositiveIntegerField(
        default=5,
        help_text='Default depreciation period'
    )
    
    # Default depreciation method
    default_depreciation_method = models.CharField(
        max_length=20, choices=DepreciationMethod.choices,
        default=DepreciationMethod.STRAIGHT_LINE
    )
    
    # For reducing balance method: depreciation rate (e.g., 20% per year)
    default_depreciation_rate_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text='Annual depreciation rate (%) for reducing balance method'
    )
    
    # GL account for assets (if finance module enabled)
    gl_account = models.CharField(
        max_length=50, blank=True,
        help_text='General Ledger account code for assets (e.g., "1200")'
    )
    accumulated_depreciation_account = models.CharField(
        max_length=50, blank=True,
        help_text='GL account for accumulated depreciation contra-asset'
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
```

### `Asset` (in `assets/models.py`)

```python
class Asset(models.Model):
    """
    Individual asset (pump, tank, vehicle, etc.).
    """
    class Status(models.TextChoices):
        ACTIVE = 'active', 'In Service'
        IDLE = 'idle', 'Idle/Not In Use'
        UNDER_MAINTENANCE = 'maintenance', 'Under Maintenance'
        DISPOSED = 'disposed', 'Disposed'

    # Identification
    asset_code = models.CharField(
        max_length=50, unique=True,
        help_text='Unique asset identifier (e.g., "PUMP-001", "TANK-A1")'
    )
    name = models.CharField(max_length=255, help_text='Asset description (e.g., "Fuel Pump - Premium Island 1")')
    
    # Category
    category = models.ForeignKey(
        AssetCategory, on_delete=models.PROTECT, related_name='assets'
    )
    
    # Acquisition
    acquisition_date = models.DateField(help_text='Date asset was purchased/capitalized')
    cost = models.DecimalField(
        max_digits=15, decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        help_text='Original/cost basis'
    )
    
    # Depreciation
    useful_life_years = models.PositiveIntegerField(
        help_text='Depreciation period in years'
    )
    depreciation_method = models.CharField(
        max_length=20, choices=AssetCategory.DepreciationMethod.choices,
        default=AssetCategory.DepreciationMethod.STRAIGHT_LINE
    )
    depreciation_rate_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='For reducing balance method'
    )
    accumulated_depreciation = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0'),
        help_text='Total depreciation to date (updated monthly)'
    )
    
    # Location & assignment
    location = models.CharField(
        max_length=255, blank=True,
        help_text='Physical location (e.g., "Main Outlet, Island 1")'
    )
    assigned_to_id = models.IntegerField(
        null=True, blank=True,
        help_text='Employee ID responsible for asset (cross-schema safe)'
    )
    
    # Status
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    
    # Residual value
    residual_value = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0'),
        help_text='Estimated scrap/salvage value'
    )
    
    # Metadata
    notes = models.TextField(blank=True)
    photo_url = models.URLField(blank=True, help_text='Link to asset photo (optional)')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['asset_code']
        indexes = [
            models.Index(fields=['category', 'status']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.asset_code} - {self.name}"

    @property
    def book_value(self) -> Decimal:
        """Current net value = cost - accumulated depreciation."""
        return self.cost - self.accumulated_depreciation

    @property
    def is_fully_depreciated(self) -> bool:
        return self.accumulated_depreciation >= self.cost

    @property
    def depreciation_remaining(self) -> Decimal:
        """Remaining deductible depreciation."""
        depreciable_base = self.cost - self.residual_value
        return max(depreciable_base - self.accumulated_depreciation, Decimal('0'))

    @property
    def age_months(self) -> int:
        """Months since acquisition."""
        from dateutil.relativedelta import relativedelta
        delta = relativedelta(date.today(), self.acquisition_date)
        return delta.years * 12 + delta.months

    def calculate_monthly_depreciation(self) -> Decimal:
        """Calculate depreciation for one month based on method."""
        if self.is_fully_depreciated or self.depreciation_method == AssetCategory.DepreciationMethod.NO_DEPRECIATION:
            return Decimal('0')
        
        depreciable_base = self.cost - self.residual_value
        
        if self.depreciation_method == AssetCategory.DepreciationMethod.STRAIGHT_LINE:
            annual = depreciable_base / Decimal(self.useful_life_years)
            return annual / Decimal(12)
        
        elif self.depreciation_method == AssetCategory.DepreciationMethod.REDUCING_BALANCE:
            annual_rate = (self.depreciation_rate_pct or Decimal('10')) / Decimal(100)
            book_value = self.book_value
            annual_depreciation = book_value * annual_rate
            return annual_depreciation / Decimal(12)
        
        return Decimal('0')
```

### `AssetAssignment` (in `assets/models.py`)

```python
class AssetAssignment(models.Model):
    """
    Track who was assigned to an asset and when. Audit trail of ownership changes.
    """
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='assignments')
    
    # Assigned to (employee or department; use IntegerField for cross-schema)
    assigned_to_id = models.IntegerField(
        help_text='Employee ID or department ID (cross-schema safe)'
    )
    assigned_to_type = models.CharField(
        max_length=20, choices=[('employee', 'Employee'), ('department', 'Department')],
        default='employee'
    )
    
    # Dates
    assigned_date = models.DateField(help_text='When assignment began')
    returned_date = models.DateField(
        null=True, blank=True,
        help_text='When asset was returned (null if currently assigned)'
    )
    
    # Status
    is_current = models.BooleanField(
        default=True,
        help_text='True if this is the active assignment'
    )
    
    notes = models.TextField(blank=True, help_text='Condition notes at assignment')
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-assigned_date']
        indexes = [
            models.Index(fields=['asset', 'is_current']),
        ]

    def __str__(self):
        return f"{self.asset.asset_code} → Staff {self.assigned_to_id} ({self.assigned_date})"

    @property
    def duration_days(self) -> int:
        """Days asset was assigned."""
        end = self.returned_date or date.today()
        return (end - self.assigned_date).days
```

### `MaintenanceLog` (in `assets/models.py`)

```python
class MaintenanceLog(models.Model):
    """
    Service, repair, or maintenance record for an asset.
    Tracks downtime and maintenance costs.
    """
    class MaintenanceType(models.TextChoices):
        PREVENTIVE = 'preventive', 'Preventive Maintenance'
        REPAIR = 'repair', 'Repair'
        INSPECTION = 'inspection', 'Inspection'
        CALIBRATION = 'calibration', 'Calibration'
        OTHER = 'other', 'Other'

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='maintenance_logs')
    
    # Type and date
    maintenance_type = models.CharField(max_length=20, choices=MaintenanceType.choices)
    performed_date = models.DateField()
    
    # Description
    description = models.TextField(help_text='What was done, what was replaced, etc.')
    performed_by = models.CharField(
        max_length=255, blank=True,
        help_text='Technician name or vendor'
    )
    
    # Cost
    cost = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        help_text='Maintenance cost (expense, not capitalized)'
    )
    
    # Downtime
    downtime_hours = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('0'),
        help_text='Hours asset was unavailable'
    )
    
    # Reference
    invoice_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-performed_date']
        indexes = [
            models.Index(fields=['asset', 'performed_date']),
        ]

    def __str__(self):
        return f"{self.asset.asset_code} - {self.get_maintenance_type_display()} ({self.performed_date})"
```

### `AssetDisposal` (in `assets/models.py`)

```python
class AssetDisposal(models.Model):
    """
    Record when asset is sold, scrapped, or retired.
    Calculates gain/loss for finance integration.
    """
    class DisposalMethod(models.TextChoices):
        SALE = 'sale', 'Sold'
        SCRAP = 'scrap', 'Scrapped'
        DONATION = 'donation', 'Donated'
        WRITE_OFF = 'write_off', 'Written Off'
        OTHER = 'other', 'Other'

    asset = models.OneToOneField(
        Asset, on_delete=models.PROTECT, related_name='disposal'
    )
    
    disposal_date = models.DateField()
    disposal_method = models.CharField(max_length=20, choices=DisposalMethod.choices)
    
    # Sale/scrap value
    proceeds = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0'),
        help_text='Cash or value received (0 if scrapped)'
    )
    
    # Gain/loss
    book_value_at_disposal = models.DecimalField(
        max_digits=15, decimal_places=2,
        help_text='Net book value on disposal date (auto-calculated)'
    )
    
    @property
    def gain_or_loss(self) -> Decimal:
        """Positive = gain, negative = loss."""
        return self.proceeds - self.book_value_at_disposal
    
    # Description
    description = models.TextField(blank=True)
    
    # Finance reference
    journal_entry_id = models.IntegerField(
        null=True, blank=True,
        help_text='JournalEntry ID if auto-journalized (optional finance integration)'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-disposal_date']

    def __str__(self):
        return f"{self.asset.asset_code} - {self.get_disposal_method_display()} ({self.disposal_date})"

    def save(self, *args, **kwargs):
        # Auto-calculate book value at disposal
        if not self.book_value_at_disposal:
            self.book_value_at_disposal = self.asset.book_value
        
        # Update asset status
        self.asset.status = Asset.Status.DISPOSED
        self.asset.save(update_fields=['status', 'updated_at'])
        
        super().save(*args, **kwargs)
```

---

## Endpoints

### `GET /api/assets/categories/`

List asset categories. Typically manager/admin only.

**Permissions**: `IsAdminOrManager`

**Response (200 OK)**:
```json
{
  "count": 5,
  "results": [
    {
      "id": 1,
      "name": "Fuel Pumps",
      "description": "Self-service fuel pump stations",
      "default_useful_life_years": 10,
      "default_depreciation_method": "straight_line",
      "gl_account": "1200",
      "is_active": true
    }
  ]
}
```

---

### `POST /api/assets/categories/`

Create asset category.

**Permissions**: `IsAdmin`

---

### `GET /api/assets/`

List assets. Filterable by category, status, assigned_to_id.

**Permissions**: `IsAuthenticated`

**Query params**:
- `category` — filter by category ID or name
- `status` — active, idle, maintenance, disposed
- `assigned_to_id` — filter by assignee
- `search` — search by asset_code or name
- `page` — pagination

**Response (200 OK)**:
```json
{
  "count": 28,
  "results": [
    {
      "id": 5,
      "asset_code": "PUMP-001",
      "name": "Fuel Pump - Premium Island 1",
      "category": {
        "id": 1,
        "name": "Fuel Pumps"
      },
      "acquisition_date": "2020-03-15",
      "cost": 12000000,
      "accumulated_depreciation": 2400000,
      "book_value": 9600000,
      "useful_life_years": 10,
      "status": "active",
      "assigned_to_id": 7,
      "location": "Main Outlet, Island 1",
      "is_fully_depreciated": false,
      "age_months": 50
    }
  ]
}
```

---

### `POST /api/assets/`

Create asset.

**Permissions**: `IsAdminOrManager`

**Request body**:
```json
{
  "asset_code": "PUMP-002",
  "name": "Fuel Pump - Diesel Island 2",
  "category_id": 1,
  "acquisition_date": "2026-04-27",
  "cost": 12500000,
  "useful_life_years": 10,
  "depreciation_method": "straight_line",
  "location": "Main Outlet, Island 2",
  "assigned_to_id": 8,
  "residual_value": 1000000,
  "notes": "New pump from supplier ABC"
}
```

---

### `GET /api/assets/{id}/`

Asset detail with full history.

**Permissions**: `IsAuthenticated`

**Response (200 OK)**:
```json
{
  "id": 5,
  "asset_code": "PUMP-001",
  "name": "Fuel Pump - Premium Island 1",
  "category": {...},
  "acquisition_date": "2020-03-15",
  "cost": 12000000,
  "accumulated_depreciation": 2400000,
  "book_value": 9600000,
  "status": "active",
  "assigned_to_id": 7,
  "location": "Main Outlet, Island 1",
  "monthly_depreciation": 100000,
  "is_fully_depreciated": false,
  "age_months": 50,
  "depreciation_remaining": 7600000,
  
  "assignments": [
    {
      "id": 1,
      "assigned_to_id": 5,
      "assigned_to_type": "employee",
      "assigned_date": "2020-03-15",
      "returned_date": "2023-06-30",
      "duration_days": 1168,
      "is_current": false
    },
    {
      "id": 2,
      "assigned_to_id": 7,
      "assigned_to_type": "employee",
      "assigned_date": "2023-07-01",
      "returned_date": null,
      "is_current": true
    }
  ],
  
  "maintenance_logs": [
    {
      "id": 3,
      "maintenance_type": "repair",
      "performed_date": "2026-01-10",
      "description": "Motor bearing replacement",
      "performed_by": "Tech Services Ltd",
      "cost": 750000,
      "downtime_hours": 8,
      "invoice_number": "TS-2026-00123"
    }
  ],
  
  "disposal": null  // or disposal record if disposed
}
```

---

### `PATCH /api/assets/{id}/`

Update asset details.

**Permissions**: `IsAdminOrManager`

---

### `POST /api/assets/{id}/assign/`

Assign asset to staff member or department.

**Permissions**: `IsAdminOrManager`

**Request body**:
```json
{
  "assigned_to_id": 9,
  "assigned_to_type": "employee",
  "notes": "Transferred from John Smith"
}
```

**Response (200 OK)**:
```json
{
  "status": "success",
  "message": "Asset assigned to employee 9",
  "assignment_id": 3
}
```

---

### `POST /api/assets/{id}/log-maintenance/`

Record maintenance/repair.

**Permissions**: `IsAuthenticated` (staff can log repairs)

**Request body**:
```json
{
  "maintenance_type": "repair",
  "performed_date": "2026-04-27",
  "description": "Seal replacement; pump tested OK",
  "performed_by": "In-house maintenance",
  "cost": 250000,
  "downtime_hours": 2,
  "invoice_number": ""
}
```

**Response (201 Created)**:
```json
{
  "id": 45,
  "asset_id": 5,
  "maintenance_type": "repair",
  "performed_date": "2026-04-27",
  "cost": 250000,
  "downtime_hours": 2
}
```

---

### `POST /api/assets/{id}/dispose/`

Record asset disposal (sale, scrap, write-off).

**Permissions**: `IsAdminOrManager`

**Request body**:
```json
{
  "disposal_method": "sale",
  "disposal_date": "2026-04-27",
  "proceeds": 3000000,
  "description": "Sold to second-hand dealer; nozzle worn"
}
```

**Response (200 OK)**:
```json
{
  "status": "success",
  "message": "Asset disposed",
  "book_value_at_disposal": 4800000,
  "proceeds": 3000000,
  "loss": 1800000
}
```

---

### `GET /api/assets/depreciation/schedule/`

Monthly depreciation schedule for financial reporting.

**Permissions**: `IsAccountant` or higher

**Query params**:
- `year` — fiscal year (default: current)
- `month` — specific month (default: all)
- `category` — filter by category

**Response (200 OK)**:
```json
{
  "year": 2026,
  "total_depreciation": {
    "january": 850000,
    "february": 850000,
    "march": 890000,
    "april": 890000
  },
  "by_asset": [
    {
      "asset_code": "PUMP-001",
      "category": "Fuel Pumps",
      "monthly": [100000, 100000, 100000, 100000]
    }
  ],
  "by_category": [
    {
      "category": "Fuel Pumps",
      "total_depreciation": 400000,
      "count_active": 4,
      "count_disposed": 1
    }
  ]
}
```

---

## Management Commands

### `calculate_monthly_depreciation`

Run monthly (typically at month-end) to record depreciation and optionally journal it.

```bash
docker compose exec backend python manage.py calculate_monthly_depreciation --month=2026-04
```

**Logic**:
1. For each active asset:
   - Calculate monthly depreciation using asset's method
   - Increment `accumulated_depreciation`
   - Save asset
2. If `--journal` flag: create JournalEntry (debit: depreciation expense, credit: accumulated depreciation)
3. Log summary: "Depreciation calculated: UGX 850,000 across 28 assets"

**File**: `assets/management/commands/calculate_monthly_depreciation.py`

---

## Finance Integration (Optional)

When depreciation is journalized, create entries in the `finance` app:

```python
def journal_depreciation(asset: Asset, depreciation_amount: Decimal, period: str):
    """Create journal entry for monthly depreciation."""
    from finance.models import JournalEntry, JournalEntryLine
    
    category = asset.category
    
    entry = JournalEntry.objects.create(
        fiscal_period_id=...,  # current fiscal period
        journal_type='depreciation',
        description=f"Monthly depreciation - {asset.asset_code}",
        source='assets',
        source_id=asset.id,
        status='posted',
    )
    
    # Debit: Depreciation Expense
    JournalEntryLine.objects.create(
        journal_entry=entry,
        account_id=...,  # depreciation expense GL account
        description=f"Depreciation - {asset.name}",
        debit=depreciation_amount,
        credit=Decimal('0'),
    )
    
    # Credit: Accumulated Depreciation
    JournalEntryLine.objects.create(
        journal_entry=entry,
        account_id=...,  # accumulated depreciation GL account
        description=f"Accumulated depreciation - {asset.name}",
        debit=Decimal('0'),
        credit=depreciation_amount,
    )
```

---

## Security & Validation

1. **Tenant isolation**: All assets scoped to tenant
2. **Depreciation method validation**: Ensure rate/useful_life are consistent
3. **Disposal isolation**: Once disposed, asset cannot be modified (read-only except for notes)
4. **Cross-schema safety**: Employee IDs stored as IntegerField; no FK across schemas
5. **Date validation**: acquisition_date must be <= today; disposal_date must be >= acquisition_date
6. **Cost validation**: All costs must be >= 0 (Decimal validators)

---

## Tests (~35 test cases)

### Location: `assets/tests.py`

#### AssetCategory Tests
- [ ] `test_create_category_with_gl_accounts` — GL account storage
- [ ] `test_useful_life_defaults` — default depreciation years
- [ ] `test_depreciation_method_choices` — method enum

#### Asset Tests
- [ ] `test_create_asset_calculates_book_value` — book_value = cost - accumulated
- [ ] `test_is_fully_depreciated_true_when_done` — depreciation complete
- [ ] `test_depreciation_remaining_calculated` — remaining = depreciable_base - accumulated
- [ ] `test_age_months_calculated` — months since acquisition
- [ ] `test_straight_line_depreciation_monthly` — monthly calculation (cost - residual) / (years * 12)
- [ ] `test_reducing_balance_depreciation_monthly` — book_value * rate / 12
- [ ] `test_fully_depreciated_asset_no_depreciation` — 0 depreciation after cost
- [ ] `test_asset_code_unique` — unique constraint
- [ ] `test_asset_status_choices` — active, idle, maintenance, disposed

#### AssetAssignment Tests
- [ ] `test_create_assignment_current` — is_current=True on new
- [ ] `test_assignment_duration_days_calculated` — (return_date - assigned_date).days
- [ ] `test_duration_uses_today_if_not_returned` — null returned_date = today
- [ ] `test_old_assignment_marked_not_current` — is_current toggle
- [ ] `test_multiple_assignments_per_asset` — history tracked
- [ ] `test_employee_vs_department_assignment` — both types supported

#### MaintenanceLog Tests
- [ ] `test_log_maintenance_recorded` — creation works
- [ ] `test_downtime_tracked` — hours stored
- [ ] `test_maintenance_cost_accumulated` — for reporting
- [ ] `test_maintenance_types_all_valid` — enum values

#### AssetDisposal Tests
- [ ] `test_create_disposal_calculates_book_value` — auto-set from asset
- [ ] `test_gain_or_loss_positive_is_gain` — proceeds > book_value
- [ ] `test_gain_or_loss_negative_is_loss` — proceeds < book_value
- [ ] `test_disposal_sets_asset_status_disposed` — asset status updated
- [ ] `test_disposed_asset_cannot_be_reassigned` — guard (optional)
- [ ] `test_asset_unique_disposal` — one disposal per asset

#### Endpoint Tests
- [ ] `test_list_assets_paginated` — GET /api/assets/ pagination
- [ ] `test_list_assets_filter_by_category` — category filter works
- [ ] `test_list_assets_filter_by_status` — status filter works
- [ ] `test_list_assets_search_by_code` — search filter works
- [ ] `test_create_asset_requires_manager` — permission check
- [ ] `test_get_asset_detail_includes_assignments` — full history returned
- [ ] `test_get_asset_detail_includes_maintenance` — maintenance logs returned
- [ ] `test_assign_asset_creates_assignment` — POST /api/assets/{id}/assign/ works
- [ ] `test_log_maintenance_creates_entry` — POST /api/assets/{id}/log-maintenance/ works
- [ ] `test_dispose_asset_calculates_gain_loss` — POST /api/assets/{id}/dispose/ calculates
- [ ] `test_depreciation_schedule_endpoint_works` — GET /api/assets/depreciation/schedule/
- [ ] `test_depreciation_schedule_filters_by_year` — year param works
- [ ] `test_depreciation_schedule_by_category` — category breakdown

#### Management Command Tests
- [ ] `test_calculate_depreciation_updates_accumulated` — command works
- [ ] `test_calculate_depreciation_skips_fully_depreciated` — no depreciation if done
- [ ] `test_calculate_depreciation_skips_disposed` — no depreciation after disposal
- [ ] `test_calculate_depreciation_respects_method` — straight-line vs reducing balance
- [ ] `test_calculate_depreciation_journals_if_requested` — optional journalization

---

## Quality Checklist

- [ ] All models have `__str__`, `ordering`, `Meta.indexes`
- [ ] Serializers created (separate Create/Read if needed)
- [ ] All DecimalField values use `Decimal()`
- [ ] All dates use `date.today()` where appropriate; `timezone.now()` for datetimes
- [ ] Depreciation calculation methods implemented correctly
- [ ] Cross-schema FKs use IntegerField (not FK)
- [ ] Asset disposal prevents reassignment (status = disposed)
- [ ] 35+ tests passing
- [ ] Security review completed
- [ ] Optional finance integration tested (if implemented)
- [ ] Documentation: `docs/modules/assets.md`

---

## Traps to Avoid

1. **Depreciation precision**: Use `Decimal()` not float; round to 2 decimals
2. **Useful life = 0**: Validate `useful_life_years > 0`
3. **Residual value > cost**: Validate `residual_value <= cost`
4. **Book value negative**: Check `accumulated_depreciation <= cost`
5. **Disposal date before acquisition**: Validate `disposal_date >= acquisition_date`
6. **Reducing balance without rate**: Ensure `depreciation_rate_pct` is set for this method
7. **Multiple current assignments**: Ensure only one assignment has `is_current=True` per asset
8. **Monthly depreciation precision**: Depreciation may not be exact; allow rounding to nearest unit

---

## Files Modified/Created

**New**:
- `backend/assets/models.py` — 5 models (Category, Asset, Assignment, MaintenanceLog, Disposal)
- `backend/assets/serializers.py`
- `backend/assets/views.py`
- `backend/assets/urls.py`
- `backend/assets/tests.py`
- `backend/assets/admin.py`
- `backend/assets/management/commands/calculate_monthly_depreciation.py`

**Modified** (if finance integration):
- `backend/finance/models.py` — optional JournalEntry integration
- `backend/finance/views.py` — optional journal creation signal

**Configuration**:
- `backend/config/settings.py` — add `'assets'` to TENANT_APPS

**Documentation**:
- `docs/modules/assets.md`

---

## Delivery Checklist

[ ] All models implemented with migrations  
[ ] All endpoints tested and secured  
[ ] Depreciation calculation working correctly  
[ ] Management command functional and cron-ready  
[ ] 35+ tests passing  
[ ] Optional finance integration tested  
[ ] Security review passed  
[ ] Documentation complete  
