"""
Transactional email helpers for the users app.
Uses Django's send_mail so the backend is configurable via EMAIL_BACKEND in settings.
"""
import logging
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

_DEFAULT_FROM = 'Nexus ERP <noreply@nexuserp.com>'


def send_invitation_email(invitation, request):
    """Send a staff invitation email."""
    scheme = 'https' if not settings.DEBUG else ('https' if request.is_secure() else 'http')
    base = getattr(settings, 'TENANT_BASE_DOMAIN', 'localhost')
    accept_url = f"{scheme}://{invitation.tenant_schema}.{base}/accept-invite?token={invitation.token}"

    subject = "You've been invited to Nexus ERP"
    body = (
        f"You have been invited to join {invitation.tenant_schema} on Nexus ERP "
        f"as a {invitation.get_role_display()}.\n\n"
        f"Click the link below to set up your account (expires in 48 hours):\n\n"
        f"{accept_url}\n\n"
        f"If you did not expect this invitation, you can ignore this email."
    )

    send_mail(
        subject=subject,
        message=body,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', _DEFAULT_FROM),
        recipient_list=[invitation.email],
        fail_silently=False,
    )
    logger.info('Invitation email sent to %s for tenant %s', invitation.email, invitation.tenant_schema)
