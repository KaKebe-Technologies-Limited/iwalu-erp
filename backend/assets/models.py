from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from datetime import date

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
        verbose_name_plural = "Asset Categories"

    def __str__(self):
        return self.name


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
        today = date.today()
        return (today.year - self.acquisition_date.year) * 12 + today.month - self.acquisition_date.month

    def calculate_monthly_depreciation(self) -> Decimal:
        """Calculate depreciation for one month based on method."""
        if self.is_fully_depreciated or self.depreciation_method == AssetCategory.DepreciationMethod.NO_DEPRECIATION:
            return Decimal('0')
        
        depreciable_base = self.cost - self.residual_value
        if depreciable_base <= 0:
            return Decimal('0')
        
        if self.depreciation_method == AssetCategory.DepreciationMethod.STRAIGHT_LINE:
            if self.useful_life_years == 0:
                return Decimal('0')
            annual = depreciable_base / Decimal(self.useful_life_years)
            return (annual / Decimal(12)).quantize(Decimal('0.01'))
        
        elif self.depreciation_method == AssetCategory.DepreciationMethod.REDUCING_BALANCE:
            annual_rate = (self.depreciation_rate_pct or Decimal('10')) / Decimal(100)
            book_value = self.book_value
            annual_depreciation = book_value * annual_rate
            return (annual_depreciation / Decimal(12)).quantize(Decimal('0.01'))
        
        return Decimal('0')


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
