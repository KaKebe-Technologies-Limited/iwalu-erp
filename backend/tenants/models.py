import uuid
from django.db import models
from django.utils import timezone
from django_tenants.models import TenantMixin, DomainMixin


class Client(TenantMixin):
    name = models.CharField(max_length=100)
    created_on = models.DateField(auto_now_add=True)

    auto_create_schema = True


class Domain(DomainMixin):
    pass


class TenantEmailVerification(models.Model):
    """
    One-time token issued at tenant registration.
    Admin user stays is_active=False until this token is consumed.
    """
    tenant = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='email_verifications')
    email = models.EmailField()
    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Verification for {self.email} ({self.tenant.schema_name})"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_used(self):
        return self.used_at is not None
