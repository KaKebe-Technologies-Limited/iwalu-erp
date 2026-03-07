from django.db import models
from outlets.models import Outlet
from products.models import Product


class Discount(models.Model):
    DISCOUNT_TYPE_CHOICES = (
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    )

    name = models.CharField(max_length=200)
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPE_CHOICES)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        if self.discount_type == 'percentage':
            return f"{self.name} ({self.value}%)"
        return f"{self.name} (UGX {self.value})"


class Shift(models.Model):
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('closed', 'Closed'),
    )

    outlet = models.ForeignKey(Outlet, on_delete=models.PROTECT, related_name='shifts')
    user_id = models.IntegerField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open')
    opening_cash = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    closing_cash = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    expected_cash = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-opened_at']

    def __str__(self):
        return f"Shift #{self.pk} - Outlet {self.outlet.name} ({self.status})"


class Sale(models.Model):
    STATUS_CHOICES = (
        ('completed', 'Completed'),
        ('voided', 'Voided'),
        ('refunded', 'Refunded'),
    )

    receipt_number = models.CharField(max_length=50, unique=True)
    outlet = models.ForeignKey(Outlet, on_delete=models.PROTECT, related_name='sales')
    shift = models.ForeignKey(Shift, on_delete=models.PROTECT, related_name='sales')
    cashier_id = models.IntegerField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    tax_total = models.DecimalField(max_digits=12, decimal_places=2)
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.ForeignKey(
        Discount, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sales',
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='completed')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.receipt_number


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='sale_items')
    product_name = models.CharField(max_length=200)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.ForeignKey(
        Discount, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sale_items',
    )
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"


class Payment(models.Model):
    PAYMENT_METHOD_CHOICES = (
        ('cash', 'Cash'),
        ('bank', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
        ('card', 'Card'),
    )

    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='payments')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.get_payment_method_display()} - {self.amount}"
