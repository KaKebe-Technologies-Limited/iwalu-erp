from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
from django.utils import timezone


class BillOfMaterials(models.Model):
    """
    Recipe defining which raw materials produce a finished product.
    One BOM per finished product (OneToOneField).
    unit_cost is a cached computed field — refresh via update_bom_costs command.
    """
    finished_product = models.OneToOneField(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='bill_of_materials',
        help_text='The product this BOM produces'
    )
    name = models.CharField(
        max_length=255,
        help_text='e.g., "Standard Bread Loaf BOM v2"'
    )
    version = models.CharField(max_length=20, default='1.0')

    # Output quantity (one full BOM batch produces this many units)
    output_quantity = models.DecimalField(
        max_digits=12, decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
        help_text='Units of finished product produced per BOM batch'
    )
    output_unit = models.CharField(
        max_length=20,
        help_text='Unit of finished product (e.g., loaves, kg, litres)'
    )

    # Cached cost (recomputed by update_bom_costs command)
    unit_cost = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0'),
        help_text='Cost per unit of finished product (total BOM cost / output_quantity)'
    )

    is_active = models.BooleanField(
        default=True,
        help_text='Inactive BOMs cannot be used to create production orders'
    )
    notes = models.TextField(blank=True)
    created_by_id = models.IntegerField(help_text='User ID who created this BOM')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['finished_product__name']
        indexes = [
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.name} → {self.finished_product.name} (v{self.version})"

    def compute_unit_cost(self) -> Decimal:
        """
        Compute cost per output unit from current BOM items and product prices.
        Does not save — call save() or use update_bom_costs command.
        """
        if self.output_quantity == Decimal('0'):
            return Decimal('0')
        total_batch_cost = sum(
            item.effective_quantity * (item.raw_material.cost_price or Decimal('0'))
            for item in self.items.select_related('raw_material').all()
        )
        return (total_batch_cost / self.output_quantity).quantize(Decimal('0.01'))


class BOMItem(models.Model):
    """
    A single raw material component in a BOM.
    waste_factor_pct adds buffer above the base quantity_required.
    effective_quantity is what actually gets deducted from stock.
    """
    bom = models.ForeignKey(
        BillOfMaterials, on_delete=models.CASCADE, related_name='items'
    )
    raw_material = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        help_text='Raw material product consumed in production'
    )
    quantity_required = models.DecimalField(
        max_digits=12, decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
        help_text='Quantity of raw material needed per BOM batch (before waste)'
    )
    unit = models.CharField(
        max_length=20,
        help_text='Unit of measurement (must match product stock unit)'
    )
    waste_factor_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text='Percentage of additional material to account for waste/shrinkage'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']
        unique_together = ('bom', 'raw_material')

    def __str__(self):
        return f"{self.bom.name} ← {self.effective_quantity} {self.unit} {self.raw_material.name}"

    @property
    def effective_quantity(self) -> Decimal:
        """Actual quantity deducted from stock, including waste buffer."""
        multiplier = Decimal('1') + (self.waste_factor_pct / Decimal('100'))
        return (self.quantity_required * multiplier).quantize(Decimal('0.001'))


class ProductionOrder(models.Model):
    """
    An order to produce a quantity of finished goods from a BOM.
    Status lifecycle: draft → in_progress → completed (or cancelled).
    Stock movements occur only on completion.
    """
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    order_number = models.CharField(
        max_length=30, unique=True,
        help_text='Auto-generated: MFG-YYYYMMDD-XXXX'
    )
    bom = models.ForeignKey(
        BillOfMaterials, on_delete=models.PROTECT, related_name='production_orders'
    )

    # Quantities
    quantity_to_produce = models.DecimalField(
        max_digits=12, decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
        help_text='Number of finished product units to produce'
    )
    quantity_produced = models.DecimalField(
        max_digits=12, decimal_places=3, default=Decimal('0'),
        help_text='Actual units produced (set at completion)'
    )

    # Status
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.DRAFT
    )

    # Timeline
    planned_start = models.DateTimeField(null=True, blank=True)
    actual_start = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Outlet where stock will be adjusted
    outlet = models.ForeignKey(
        'outlets.Outlet', on_delete=models.PROTECT,
        help_text='Outlet whose stock is adjusted on completion'
    )

    # Staff (cross-schema safe)
    ordered_by_id = models.IntegerField(help_text='User ID who created the order')

    # Computed at completion
    total_material_cost = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0'),
        help_text='Sum of raw material costs at time of production'
    )

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'outlet']),
            models.Index(fields=['bom']),
        ]

    def __str__(self):
        return f"{self.order_number} — {self.bom.finished_product.name} ×{self.quantity_to_produce}"

    def get_required_materials(self) -> list[dict]:
        """
        Return list of {raw_material, quantity_needed} for this production run.
        quantity_needed = BOMItem.effective_quantity × (quantity_to_produce / bom.output_quantity)
        """
        if self.bom.output_quantity == Decimal('0'):
            return []
        scale = self.quantity_to_produce / self.bom.output_quantity
        return [
            {
                'raw_material': item.raw_material,
                'quantity_needed': (item.effective_quantity * scale).quantize(Decimal('0.001')),
                'unit': item.unit,
            }
            for item in self.bom.items.select_related('raw_material').all()
        ]


class ProductionOrderItem(models.Model):
    """
    Actual materials consumed in a completed production run.
    Created at completion time from BOM data + actual quantities.
    Serves as the permanent audit record of raw material consumption.
    """
    production_order = models.ForeignKey(
        ProductionOrder, on_delete=models.CASCADE, related_name='consumed_materials'
    )
    raw_material = models.ForeignKey(
        'products.Product', on_delete=models.PROTECT
    )
    quantity_planned = models.DecimalField(
        max_digits=12, decimal_places=3,
        help_text='Quantity from BOM calculation'
    )
    quantity_actual = models.DecimalField(
        max_digits=12, decimal_places=3,
        help_text='Actual quantity consumed (may differ due to waste)'
    )
    unit = models.CharField(max_length=20)
    unit_cost = models.DecimalField(
        max_digits=15, decimal_places=2,
        help_text='Cost per unit at time of production'
    )
    line_cost = models.DecimalField(
        max_digits=15, decimal_places=2,
        help_text='quantity_actual × unit_cost'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.production_order.order_number} ← {self.quantity_actual} {self.unit} {self.raw_material.name}"


class WorkInProgress(models.Model):
    """
    Snapshot of a production order's progress at a point in time.
    Purely informational — does not affect stock.
    """
    production_order = models.ForeignKey(
        ProductionOrder, on_delete=models.CASCADE, related_name='wip_snapshots'
    )
    snapshot_date = models.DateField()
    materials_consumed_value = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0'),
        help_text='Estimated value of materials used so far'
    )
    percentage_complete = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
        help_text='Estimated completion percentage (0–100)'
    )
    notes = models.TextField(blank=True)
    recorded_by_id = models.IntegerField(help_text='User ID who recorded this snapshot')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-snapshot_date']
        indexes = [
            models.Index(fields=['production_order', 'snapshot_date']),
        ]

    def __str__(self):
        return f"{self.production_order.order_number} WIP — {self.percentage_complete}% ({self.snapshot_date})"
