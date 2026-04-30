from django.db import models


class Notification(models.Model):
    CHANNEL_CHOICES = (
        ('in_app', 'In-App'),
        ('email', 'Email'),
        ('sms', 'SMS'),
    )
    TYPE_CHOICES = (
        ('low_fuel', 'Low Fuel'),
        ('low_stock', 'Low Stock'),
        ('variance_alert', 'Variance Alert'),
        ('shift_reminder', 'Shift Reminder'),
        ('payment_failure', 'Payment Failure'),
        ('approval_required', 'Approval Required'),
        ('system', 'System'),
    )
    PRIORITY_CHOICES = (
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('critical', 'Critical'),
    )

    recipient_id = models.IntegerField(db_index=True)
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default='in_app')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    title = models.CharField(max_length=255)
    body = models.TextField()
    source_type = models.CharField(
        max_length=50, blank=True,
        help_text='Model name that triggered this notification (e.g. FuelReconciliation)',
    )
    reference_id = models.IntegerField(
        null=True, blank=True,
        help_text='PK of the source object',
    )
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient_id', '-created_at']),
            models.Index(fields=['recipient_id', 'read_at']),
            models.Index(fields=['notification_type', '-created_at']),
        ]

    def __str__(self):
        return f"[{self.notification_type}] {self.title} -> user #{self.recipient_id}"

    @property
    def is_read(self):
        return self.read_at is not None


class NotificationPreference(models.Model):
    CHANNEL_CHOICES = Notification.CHANNEL_CHOICES
    TYPE_CHOICES = Notification.TYPE_CHOICES

    user_id = models.IntegerField(db_index=True)
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default='in_app')
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['notification_type', 'channel']
        unique_together = ('user_id', 'notification_type', 'channel')

    def __str__(self):
        status = 'ON' if self.is_enabled else 'OFF'
        return f"user #{self.user_id}: {self.notification_type}/{self.channel} = {status}"


class NotificationTemplate(models.Model):
    CHANNEL_CHOICES = Notification.CHANNEL_CHOICES
    TYPE_CHOICES = Notification.TYPE_CHOICES

    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES)
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField(
        help_text='Template body. Use {variable_name} placeholders.',
    )
    variables = models.JSONField(
        default=list, blank=True,
        help_text='List of variable names available in this template.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['notification_type', 'channel']
        unique_together = ('notification_type', 'channel')

    def __str__(self):
        return f"Template: {self.notification_type}/{self.channel}"

    def render(self, context):
        """Render template body with the given context dict, escaping HTML."""
        from django.utils.html import escape

        allowed_vars = set(self.variables) if self.variables else None
        rendered_body = self.body
        rendered_subject = self.subject
        for key, value in context.items():
            if allowed_vars and key not in allowed_vars:
                continue
            safe_value = escape(str(value))
            rendered_body = rendered_body.replace(f'{{{key}}}', safe_value)
            rendered_subject = rendered_subject.replace(f'{{{key}}}', safe_value)
        return rendered_subject, rendered_body
