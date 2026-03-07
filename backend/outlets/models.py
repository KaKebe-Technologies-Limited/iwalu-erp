from django.db import models


class Outlet(models.Model):
    OUTLET_TYPE_CHOICES = (
        ('fuel_station', 'Fuel Station'),
        ('cafe', 'Cafe'),
        ('supermarket', 'Supermarket'),
        ('boutique', 'Boutique'),
        ('bridal', 'Bridal'),
        ('general', 'General'),
    )

    name = models.CharField(max_length=200)
    outlet_type = models.CharField(max_length=20, choices=OUTLET_TYPE_CHOICES)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_outlet_type_display()})"
