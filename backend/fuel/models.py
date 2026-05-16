from django.db import models


class Pump(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('maintenance', 'Under Maintenance'),
    )

    outlet = models.ForeignKey(
        'outlets.Outlet', on_delete=models.PROTECT, related_name='pumps',
    )
    product = models.ForeignKey(
        'products.Product', on_delete=models.PROTECT, related_name='pumps',
    )
    pump_number = models.PositiveIntegerField()
    name = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['outlet', 'pump_number']
        unique_together = ('outlet', 'pump_number')

    def __str__(self):
        return f"Pump {self.pump_number} - {self.outlet.name}"


class Tank(models.Model):
    outlet = models.ForeignKey(
        'outlets.Outlet', on_delete=models.PROTECT, related_name='tanks',
    )
    product = models.ForeignKey(
        'products.Product', on_delete=models.PROTECT, related_name='tanks',
    )
    name = models.CharField(max_length=100)
    capacity = models.DecimalField(max_digits=12, decimal_places=3)
    current_level = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    reorder_level = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['outlet', 'name']

    def __str__(self):
        return f"{self.name} - {self.outlet.name}"

    @property
    def fill_percentage(self):
        if self.capacity <= 0:
            return 0
        return round(float(self.current_level / self.capacity) * 100, 1)

    @property
    def is_low(self):
        return self.current_level <= self.reorder_level


class TankReading(models.Model):
    READING_TYPE_CHOICES = (
        ('manual', 'Manual Dip'),
        ('automatic', 'Automatic Gauge'),
        ('delivery', 'Post-Delivery'),
        ('reconciliation', 'Reconciliation'),
    )

    tank = models.ForeignKey(Tank, on_delete=models.CASCADE, related_name='readings')
    reading_level = models.DecimalField(max_digits=12, decimal_places=3)
    reading_type = models.CharField(max_length=15, choices=READING_TYPE_CHOICES)
    recorded_by = models.IntegerField()
    notes = models.TextField(blank=True)
    reading_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-reading_at']
        indexes = [
            models.Index(fields=['tank', 'reading_at']),
        ]

    def __str__(self):
        return f"{self.tank.name}: {self.reading_level}L @ {self.reading_at}"


class PumpReading(models.Model):
    pump = models.ForeignKey(Pump, on_delete=models.CASCADE, related_name='readings')
    shift = models.ForeignKey(
        'sales.Shift', on_delete=models.PROTECT, related_name='pump_readings',
    )
    opening_reading = models.DecimalField(max_digits=12, decimal_places=3)
    closing_reading = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True,
    )
    recorded_by = models.IntegerField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('pump', 'shift')
        indexes = [
            models.Index(fields=['pump', 'created_at']),
        ]

    def __str__(self):
        return f"Pump {self.pump.pump_number} - Shift #{self.shift_id}"

    @property
    def volume_dispensed(self):
        if self.closing_reading is not None and self.opening_reading is not None:
            return self.closing_reading - self.opening_reading
        return None


class FuelDelivery(models.Model):
    tank = models.ForeignKey(Tank, on_delete=models.PROTECT, related_name='deliveries')
    supplier = models.ForeignKey(
        'inventory.Supplier', on_delete=models.PROTECT, related_name='fuel_deliveries',
    )
    delivery_date = models.DateTimeField()
    volume_ordered = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True,
    )
    volume_received = models.DecimalField(max_digits=12, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2)
    delivery_note_number = models.CharField(max_length=100, blank=True)
    tank_level_before = models.DecimalField(max_digits=12, decimal_places=3)
    tank_level_after = models.DecimalField(max_digits=12, decimal_places=3)
    received_by = models.IntegerField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-delivery_date']
        indexes = [
            models.Index(fields=['tank', 'delivery_date']),
        ]

    def __str__(self):
        return f"Delivery to {self.tank.name}: {self.volume_received}L"


class FuelReconciliation(models.Model):
    VARIANCE_TYPE_CHOICES = (
        ('gain', 'Gain'),
        ('loss', 'Loss'),
        ('within_tolerance', 'Within Tolerance'),
    )
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
    )

    date = models.DateField()
    outlet = models.ForeignKey(
        'outlets.Outlet', on_delete=models.PROTECT, related_name='fuel_reconciliations',
    )
    tank = models.ForeignKey(Tank, on_delete=models.PROTECT, related_name='reconciliations')
    opening_stock = models.DecimalField(max_digits=12, decimal_places=3)
    closing_stock = models.DecimalField(max_digits=12, decimal_places=3)
    total_received = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    total_dispensed = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    expected_closing = models.DecimalField(max_digits=12, decimal_places=3)
    variance = models.DecimalField(max_digits=12, decimal_places=3)
    variance_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    variance_type = models.CharField(max_length=20, choices=VARIANCE_TYPE_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True)
    reconciled_by = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        unique_together = ('date', 'tank')
        indexes = [
            models.Index(fields=['outlet', 'date']),
            models.Index(fields=['variance_type', 'date']),
        ]

    def __str__(self):
        return f"Reconciliation: {self.tank.name} on {self.date}"


class PumpEvent(models.Model):
    """
    Hardware event received from a pump controller (real or mock).
    The pump-events API endpoint writes here; completed events auto-update PumpReading.
    source='hardware' requires X-Pump-API-Key authentication.
    source='mock' is used by the development mock controller.
    source='manual' is used by attendants recording events manually via the app.
    """
    EVENT_TYPE_CHOICES = (
        ('authorised', 'Authorised'),
        ('flowing', 'Flowing'),
        ('completed', 'Completed'),
        ('error', 'Error'),
    )
    SOURCE_CHOICES = (
        ('hardware', 'Hardware Controller'),
        ('mock', 'Mock Controller'),
        ('manual', 'Manual Entry'),
    )

    pump = models.ForeignKey(
        Pump, on_delete=models.PROTECT, related_name='events',
    )
    event_type = models.CharField(max_length=15, choices=EVENT_TYPE_CHOICES)
    litres = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True,
        help_text='Total litres dispensed. Only set on completed events.',
    )
    amount_ugx = models.DecimalField(
        max_digits=12, decimal_places=0, null=True, blank=True,
        help_text='Sale amount in UGX. Only set on completed events.',
    )
    meter_start = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True,
        help_text='Pump odometer reading at start of dispense.',
    )
    meter_end = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True,
        help_text='Pump odometer reading at end of dispense.',
    )
    attendant_id = models.IntegerField(
        null=True, blank=True,
        help_text='User ID of the attendant on duty. Set by the app, not the hardware.',
    )
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='hardware')
    raw_payload = models.JSONField(
        default=dict,
        help_text='Raw payload as received from the controller, for debugging.',
    )
    occurred_at = models.DateTimeField(
        help_text='When the event occurred according to the hardware clock.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-occurred_at']
        indexes = [
            models.Index(fields=['pump', 'occurred_at']),
            models.Index(fields=['event_type', 'occurred_at']),
        ]

    def __str__(self):
        return f"Pump {self.pump.pump_number} {self.event_type} @ {self.occurred_at}"
