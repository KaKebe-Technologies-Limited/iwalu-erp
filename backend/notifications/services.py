import logging
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import Notification, NotificationPreference, NotificationTemplate

logger = logging.getLogger(__name__)


def create_notification(recipient_id, notification_type, title, body,
                        channel='in_app', priority='normal',
                        source_type='', reference_id=None):
    """Create a notification, respecting user preferences."""
    # Check user preference
    pref = NotificationPreference.objects.filter(
        user_id=recipient_id,
        notification_type=notification_type,
        channel=channel,
    ).first()

    if pref and not pref.is_enabled:
        logger.info(
            'Notification suppressed: user %s opted out of %s/%s',
            recipient_id, notification_type, channel,
        )
        return None

    notification = Notification.objects.create(
        recipient_id=recipient_id,
        notification_type=notification_type,
        channel=channel,
        priority=priority,
        title=title,
        body=body,
        source_type=source_type,
        reference_id=reference_id,
    )

    if channel == 'email':
        _queue_email(notification)
    elif channel == 'sms':
        _queue_sms(notification)

    return notification


def create_notification_from_template(recipient_id, notification_type,
                                      context, channel='in_app',
                                      priority='normal',
                                      source_type='', reference_id=None):
    """Create a notification using a registered template."""
    template = NotificationTemplate.objects.filter(
        notification_type=notification_type,
        channel=channel,
        is_active=True,
    ).first()

    if not template:
        logger.warning(
            'No active template for %s/%s, falling back to manual.',
            notification_type, channel,
        )
        return None

    subject, body = template.render(context)
    return create_notification(
        recipient_id=recipient_id,
        notification_type=notification_type,
        title=subject,
        body=body,
        channel=channel,
        priority=priority,
        source_type=source_type,
        reference_id=reference_id,
    )


def mark_read(notification_id, user_id):
    """Mark a single notification as read."""
    notification = Notification.objects.filter(
        pk=notification_id, recipient_id=user_id,
    ).first()
    if not notification:
        raise ValidationError({'detail': 'Notification not found.'})
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=['read_at', 'updated_at'])
    return notification


def mark_all_read(user_id, notification_type=None):
    """Mark all unread notifications as read for a user."""
    qs = Notification.objects.filter(recipient_id=user_id, read_at__isnull=True)
    if notification_type:
        qs = qs.filter(notification_type=notification_type)
    count = qs.update(read_at=timezone.now())
    return count


def get_unread_count(user_id):
    """Return the count of unread in-app notifications."""
    return Notification.objects.filter(
        recipient_id=user_id, read_at__isnull=True, channel='in_app',
    ).count()


# ---------- Alert triggers (called from other modules) ----------

def notify_low_fuel(tank, recipient_ids):
    """Send low-fuel alert to a list of users."""
    for uid in recipient_ids:
        create_notification(
            recipient_id=uid,
            notification_type='low_fuel',
            title=f'Low fuel: {tank.name}',
            body=(
                f'Tank "{tank.name}" at {tank.outlet.name} is at '
                f'{tank.fill_percentage}% ({tank.current_level}L / '
                f'{tank.capacity}L). Reorder level: {tank.reorder_level}L.'
            ),
            priority='high',
            source_type='Tank',
            reference_id=tank.pk,
        )


def notify_low_stock(product, outlet, current_qty, reorder_level, recipient_ids):
    """Send low-stock alert to a list of users."""
    for uid in recipient_ids:
        create_notification(
            recipient_id=uid,
            notification_type='low_stock',
            title=f'Low stock: {product.name}',
            body=(
                f'Product "{product.name}" at {outlet.name} is at '
                f'{current_qty} units. Reorder level: {reorder_level}.'
            ),
            priority='high',
            source_type='Product',
            reference_id=product.pk,
        )


def notify_variance_alert(reconciliation, recipient_ids):
    """Send variance alert when reconciliation detects non-tolerable variance."""
    for uid in recipient_ids:
        create_notification(
            recipient_id=uid,
            notification_type='variance_alert',
            title=f'Fuel variance: {reconciliation.tank.name}',
            body=(
                f'Reconciliation on {reconciliation.date} for tank '
                f'"{reconciliation.tank.name}" at {reconciliation.outlet.name} '
                f'shows a {reconciliation.variance_type} of '
                f'{abs(reconciliation.variance)}L '
                f'({abs(reconciliation.variance_percentage)}%).'
            ),
            priority='critical',
            source_type='FuelReconciliation',
            reference_id=reconciliation.pk,
        )


def notify_approval_required(transaction_type, amount, requester_name,
                             reference_id, recipient_ids):
    """Send approval-required notification."""
    for uid in recipient_ids:
        create_notification(
            recipient_id=uid,
            notification_type='approval_required',
            title=f'Approval needed: {transaction_type}',
            body=(
                f'{requester_name} has submitted a {transaction_type} '
                f'of {amount} requiring your approval.'
            ),
            priority='high',
            source_type=transaction_type,
            reference_id=reference_id,
        )


# ---------- Delivery helpers ----------

def _queue_email(notification):
    """Send notification email synchronously via Django's email backend."""
    from django.conf import settings
    from django.core.mail import send_mail
    from django.contrib.auth import get_user_model

    User = get_user_model()
    try:
        user = User.objects.get(pk=notification.recipient_id)
    except User.DoesNotExist:
        logger.warning('Email skipped — user #%s not found', notification.recipient_id)
        return

    try:
        send_mail(
            subject=notification.title,
            message=notification.body,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@nexuserp.com'),
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info('Email sent: [%s] -> %s', notification.notification_type, user.email)
    except Exception:
        logger.exception('Email delivery failed for notification #%s', notification.pk)


def _queue_sms(notification):
    """SMS delivery — stub until an SMS provider is integrated."""
    logger.info('SMS queued (not yet delivered): [%s] %s -> user #%s',
                notification.notification_type, notification.title,
                notification.recipient_id)
