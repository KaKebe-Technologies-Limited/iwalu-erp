from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal


class MenuCategory(models.Model):
    """
    Grouping for menu items (e.g. Drinks, Hot Food, Pastries, Combos).
    Admin-managed. Controls display order on POS/menu board.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name_plural = 'Menu Categories'

    def __str__(self):
        return self.name


class MenuItem(models.Model):
    """
    A single item on the café or bakery menu.
    If has_bom=True, creating an order deducts ingredients from OutletStock.
    cost_price is denormalised — recompute whenever BOM changes.
    """
    name = models.CharField(max_length=200)
    category = models.ForeignKey(
        MenuCategory, on_delete=models.PROTECT, related_name='items'
    )
    description = models.TextField(blank=True)

    # Pricing
    price = models.DecimalField(
        max_digits=15, decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        help_text='Selling price (UGX)'
    )
    cost_price = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0'),
        help_text='Computed from BOM ingredients. Update via update-bom action.'
    )

    # BOM toggle
    has_bom = models.BooleanField(
        default=False,
        help_text='True if ingredients must be deducted from stock on order'
    )

    # Availability
    is_available = models.BooleanField(
        default=True,
        help_text='Unavailable items cannot be ordered, even if in stock'
    )

    preparation_time_minutes = models.PositiveIntegerField(
        default=0,
        help_text='Estimated prep time; shown to kitchen staff'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'name']
        indexes = [
            models.Index(fields=['category', 'is_available']),
        ]

    def __str__(self):
        return f"{self.name} (UGX {self.price})"

    def recompute_cost_price(self):
        """Recompute and save cost_price from BOM ingredients."""
        if not self.has_bom:
            return
        total = sum(
            ing.product.cost_price * ing.quantity_per_serving
            for ing in self.ingredients.select_related('product').all()
            if hasattr(ing.product, 'cost_price') and ing.product.cost_price
        )
        self.cost_price = total
        self.save(update_fields=['cost_price', 'updated_at'])


class MenuItemIngredient(models.Model):
    """
    BOM line: links a MenuItem to an inventory Product.
    quantity_per_serving is deducted from OutletStock when ordered.
    """
    UNIT_CHOICES = [
        ('g', 'Grams'), ('kg', 'Kilograms'),
        ('ml', 'Millilitres'), ('l', 'Litres'),
        ('pcs', 'Pieces'), ('tbsp', 'Tablespoon'), ('tsp', 'Teaspoon'),
    ]

    menu_item = models.ForeignKey(
        MenuItem, on_delete=models.CASCADE, related_name='ingredients'
    )
    product = models.ForeignKey(
        'products.Product', on_delete=models.PROTECT,
        help_text='Inventory product used as ingredient'
    )
    quantity_per_serving = models.DecimalField(
        max_digits=12, decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
        help_text='How much of this product is used per serving'
    )
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['menu_item', 'id']
        unique_together = ('menu_item', 'product')

    def __str__(self):
        return f"{self.menu_item.name} ← {self.quantity_per_serving}{self.unit} {self.product.name}"


class MenuOrder(models.Model):
    """
    A café/bakery order (dine-in or takeaway).
    Stock is deducted at creation time inside a transaction.
    """
    class OrderType(models.TextChoices):
        DINE_IN = 'dine_in', 'Dine-In'
        TAKEAWAY = 'takeaway', 'Takeaway'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending (received)'
        PREPARING = 'preparing', 'Being Prepared'
        READY = 'ready', 'Ready for Collection / Service'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    order_number = models.CharField(
        max_length=30, unique=True,
        help_text='Auto-generated: ORD-YYYYMMDD-XXXX'
    )
    order_type = models.CharField(max_length=10, choices=OrderType.choices)
    table_number = models.CharField(
        max_length=20, blank=True,
        help_text='Table reference for dine-in orders'
    )
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.PENDING
    )

    # Cashier who created the order (cross-schema IntegerField)
    cashier_id = models.IntegerField(help_text='User ID of cashier')

    total_amount = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0'),
        help_text='Sum of order item line totals'
    )
    notes = models.TextField(blank=True, help_text='Special instructions for kitchen')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['order_type']),
        ]

    def __str__(self):
        return f"{self.order_number} ({self.get_order_type_display()}, {self.status})"


class MenuOrderItem(models.Model):
    """
    A single line on a MenuOrder. Stock deduction happens at order creation.
    """
    order = models.ForeignKey(
        MenuOrder, on_delete=models.CASCADE, related_name='items'
    )
    menu_item = models.ForeignKey(
        MenuItem, on_delete=models.PROTECT
    )
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )
    unit_price = models.DecimalField(
        max_digits=15, decimal_places=2,
        help_text='Price at time of order (snapshot)'
    )
    line_total = models.DecimalField(max_digits=15, decimal_places=2)
    special_instructions = models.TextField(blank=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.quantity}× {self.menu_item.name} on {self.order.order_number}"

    def save(self, *args, **kwargs):
        self.line_total = self.unit_price * Decimal(self.quantity)
        super().save(*args, **kwargs)


class WasteLog(models.Model):
    """
    Records ingredient waste, spoilage, or expiry.
    Does NOT deduct stock (assumes stock was already consumed or adjusted separately).
    Used for reporting and trend analysis.
    """
    class Reason(models.TextChoices):
        EXPIRED = 'expired', 'Expired'
        SPOILED = 'spoiled', 'Spoiled'
        OVERPRODUCTION = 'overproduction', 'Overproduction'
        SPILLAGE = 'spillage', 'Spillage/Breakage'
        OTHER = 'other', 'Other'

    product = models.ForeignKey(
        'products.Product', on_delete=models.PROTECT,
        help_text='Ingredient/product that was wasted'
    )
    quantity = models.DecimalField(
        max_digits=12, decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))]
    )
    unit = models.CharField(max_length=10)
    reason = models.CharField(max_length=20, choices=Reason.choices)
    cost_value = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        help_text='Estimated loss value (quantity × cost price). Auto-computed if blank.'
    )

    recorded_by_id = models.IntegerField(help_text='User ID who logged the waste')
    recorded_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['product', 'recorded_at']),
            models.Index(fields=['reason']),
        ]

    def __str__(self):
        return f"{self.quantity}{self.unit} {self.product.name} — {self.get_reason_display()}"

    def save(self, *args, **kwargs):
        if self.cost_value is None and hasattr(self.product, 'cost_price') and self.product.cost_price:
            self.cost_value = Decimal(str(self.product.cost_price)) * Decimal(str(self.quantity))
        super().save(*args, **kwargs)
