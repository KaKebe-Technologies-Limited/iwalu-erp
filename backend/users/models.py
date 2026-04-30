import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('manager', 'Manager'),
        ('cashier', 'Cashier'),
        ('attendant', 'Attendant'),
        ('accountant', 'Accountant'),
    )
    
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='cashier')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']
    
    def __str__(self):
        return f'{self.email} ({self.role})'
    
    class Meta:
        ordering = ['-created_at']


class UserInvitation(models.Model):
    """
    Email invitation issued by a tenant admin to onboard a new staff member.
    Stored in the public schema. tenant_schema ties the invite to a specific tenant.
    The invitee accepts at schema.nexus.com/accept-invite?token=<token>.
    """
    ROLE_CHOICES = User.ROLE_CHOICES

    email = models.EmailField(db_index=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='cashier')
    tenant_schema = models.CharField(max_length=63, db_index=True)
    invited_by_id = models.IntegerField()
    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('email', 'tenant_schema')

    def __str__(self):
        return f"Invite {self.email} to {self.tenant_schema} as {self.role}"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_accepted(self):
        return self.accepted_at is not None

    @property
    def is_pending(self):
        return not self.is_accepted and not self.is_expired
