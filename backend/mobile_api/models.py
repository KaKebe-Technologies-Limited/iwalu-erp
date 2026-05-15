from django.db import models


class MobileSyncLog(models.Model):
    """
    Audit record written each time a mobile device completes a batch sync.
    Stored per-tenant (app is in TENANT_APPS).
    Uses IntegerField for shift/user/outlet references — cross-schema FK
    not possible with django-tenants.
    """
    device_id = models.CharField(max_length=255)
    shift_id = models.IntegerField()
    user_id = models.IntegerField()
    outlet_id = models.IntegerField()
    transaction_count = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    synced_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-synced_at']
        indexes = [
            models.Index(fields=['shift_id', 'synced_at']),
        ]

    def __str__(self):
        return (
            f"Sync shift={self.shift_id} by device={self.device_id} "
            f"at {self.synced_at}"
        )
