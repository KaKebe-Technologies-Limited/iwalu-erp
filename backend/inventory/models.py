from django.db import models
from outlets.models import Outlet
from products.models import Product


class Supplier(models.Model):
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class OutletStock(models.Model):
    outlet = models.ForeignKey(Outlet, on_delete=models.CASCADE, related_name='stock_levels')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='outlet_stocks')
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('outlet', 'product')
        ordering = ['outlet', 'product']

    def __str__(self):
        return f"{self.product.name} @ {self.outlet.name}: {self.quantity}"


class PurchaseOrder(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('pending_approval', 'Pending Approval'),
        ('submitted', 'Submitted'),
        ('partial', 'Partially Received'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
        ('rejected', 'Rejected'),
    )

    po_number = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='purchase_orders')
    outlet = models.ForeignKey(Outlet, on_delete=models.PROTECT, related_name='purchase_orders')
    ordered_by = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    expected_date = models.DateField(null=True, blank=True)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    approval_request = models.ForeignKey(
        'approvals.ApprovalRequest', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='purchase_orders'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.po_number


class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='po_items')
    quantity_ordered = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_received = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.product.name} x {self.quantity_ordered}"


class StockTransfer(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('in_transit', 'In Transit'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )

    transfer_number = models.CharField(max_length=50, unique=True)
    from_outlet = models.ForeignKey(
        Outlet, on_delete=models.PROTECT, related_name='transfers_out',
    )
    to_outlet = models.ForeignKey(
        Outlet, on_delete=models.PROTECT, related_name='transfers_in',
    )
    initiated_by = models.IntegerField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.transfer_number


class StockTransferItem(models.Model):
    transfer = models.ForeignKey(StockTransfer, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='transfer_items')
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_received = models.DecimalField(max_digits=12, decimal_places=3, default=0)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


class StockAuditLog(models.Model):
    MOVEMENT_TYPE_CHOICES = (
        ('sale', 'Sale'),
        ('void', 'Void'),
        ('adjustment', 'Adjustment'),
        ('transfer_out', 'Transfer Out'),
        ('transfer_in', 'Transfer In'),
        ('purchase', 'Purchase'),
    )

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='audit_logs')
    outlet = models.ForeignKey(
        Outlet, on_delete=models.CASCADE, related_name='audit_logs',
        null=True, blank=True,
    )
    movement_type = models.CharField(max_length=15, choices=MOVEMENT_TYPE_CHOICES)
    quantity_change = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_before = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_after = models.DecimalField(max_digits=12, decimal_places=3)
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.IntegerField(null=True, blank=True)
    user_id = models.IntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', 'created_at']),
            models.Index(fields=['outlet', 'created_at']),
        ]

    def __str__(self):
        return f"{self.get_movement_type_display()}: {self.product.name} ({self.quantity_change:+})"
