from django.db import models


class Category(models.Model):
    BUSINESS_UNIT_CHOICES = (
        ('fuel', 'Fuel'),
        ('cafe', 'Cafe'),
        ('supermarket', 'Supermarket'),
        ('boutique', 'Boutique'),
        ('bridal', 'Bridal'),
        ('general', 'General'),
    )

    name = models.CharField(max_length=200)
    business_unit = models.CharField(max_length=20, choices=BUSINESS_UNIT_CHOICES)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='children',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'categories'

    def __str__(self):
        return f"{self.name} ({self.get_business_unit_display()})"


class Product(models.Model):
    UNIT_CHOICES = (
        ('piece', 'Piece'),
        ('litre', 'Litre'),
        ('kg', 'Kilogram'),
        ('metre', 'Metre'),
        ('box', 'Box'),
        ('pack', 'Pack'),
    )

    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, unique=True)
    barcode = models.CharField(max_length=100, blank=True)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name='products',
    )
    cost_price = models.DecimalField(max_digits=12, decimal_places=2)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    track_stock = models.BooleanField(default=True)
    stock_quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    reorder_level = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='piece')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.sku})"

    @property
    def is_low_stock(self):
        return self.track_stock and self.stock_quantity <= self.reorder_level
