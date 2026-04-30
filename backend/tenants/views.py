"""
Tenant self-service registration and email verification.

Security posture:
  - Registration disabled by default (TENANT_SELF_REGISTRATION_ENABLED=True to enable).
    While disabled returns 503 — removes the abuse vector entirely during private beta.
  - Per-IP rate-limited (AnonRateThrottle 'tenant-registration' scope).
  - On success returns 201 with pending status but NO JWT tokens. The admin user
    is is_active=False until the email verification link is clicked.
  - Verification token expires in 24 hours and is single-use.
  - Raw exceptions are never surfaced to anonymous callers (leaks Postgres internals).
"""
import logging
from datetime import timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django_tenants.utils import schema_context, get_public_schema_name
from rest_framework import status, viewsets
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes, throttle_classes, action
)
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import User
from .models import (
    Client, Domain, TenantEmailVerification,
    SubscriptionPlan, TenantSubscription, SubscriptionInvoice
)
from .serializers import (
    TenantRegistrationSerializer, SubscriptionPlanSerializer,
    TenantSubscriptionSerializer, SubscriptionInvoiceSerializer,
    ChangePlanSerializer, ResendVerificationSerializer
)

logger = logging.getLogger(__name__)

_DEFAULT_FROM = 'Nexus ERP <noreply@nexuserp.com>'
_VERIFICATION_EXPIRY_HOURS = 24


class TenantRegistrationThrottle(AnonRateThrottle):
    scope = 'tenant-registration'


def _scheme_for(request) -> str:
    if not settings.DEBUG:
        return 'https'
    return 'https' if request.is_secure() else 'http'


def _send_verification_email(admin_email, token, tenant_schema, scheme, base_domain):
    """Send the email-verification link to the new admin."""
    verify_url = f"{scheme}://{base_domain}/api/tenants/verify-email/?token={token}"
    send_mail(
        subject='Verify your Nexus ERP account',
        message=(
            f"Welcome to Nexus ERP!\n\n"
            f"Your business subdomain will be: {tenant_schema}.{base_domain}\n\n"
            f"Click the link below to verify your email and activate your account "
            f"(expires in {_VERIFICATION_EXPIRY_HOURS} hours):\n\n"
            f"{verify_url}\n\n"
            f"If you did not create a Nexus ERP account, you can ignore this email."
        ),
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', _DEFAULT_FROM),
        recipient_list=[admin_email],
        fail_silently=False,
    )


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([TenantRegistrationThrottle])
def register_tenant(request):
    """
    Public self-service tenant registration.

    Creates a Client + Domain + first admin user atomically. The admin user is
    is_active=False until the email verification link is clicked.
    """
    if not getattr(settings, 'TENANT_SELF_REGISTRATION_ENABLED', False):
        return Response(
            {
                'error': 'Self-service registration is currently disabled.',
                'detail': 'Contact sales@kakebe.com to provision a new tenant.',
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    serializer = TenantRegistrationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    base_domain = getattr(settings, 'TENANT_BASE_DOMAIN', 'localhost')
    full_domain = f"{data['schema_name']}.{base_domain}"
    scheme = _scheme_for(request)

    try:
        with schema_context(get_public_schema_name()):
            with transaction.atomic():
                client = Client.objects.create(
                    schema_name=data['schema_name'],
                    name=data['business_name'],
                )
                Domain.objects.create(
                    domain=full_domain,
                    tenant=client,
                    is_primary=True,
                )
                admin = User.objects.create(
                    email=data['admin_email'],
                    username=data['admin_username'],
                    first_name=data['admin_first_name'],
                    last_name=data['admin_last_name'],
                    phone_number=data.get('admin_phone', ''),
                    role='admin',
                    is_active=False,
                    is_staff=False,
                    is_superuser=False,
                )
                admin.set_password(data['admin_password'])
                admin.save()

                verification = TenantEmailVerification.objects.create(
                    tenant=client,
                    email=data['admin_email'],
                    expires_at=timezone.now() + timedelta(hours=_VERIFICATION_EXPIRY_HOURS),
                )

                # Create subscription (Trial by default)
                plan = SubscriptionPlan.objects.get(id=data['plan_id'])
                trial_days = getattr(settings, 'TRIAL_DAYS', 14)
                now = timezone.now()
                TenantSubscription.objects.create(
                    tenant=client,
                    plan=plan,
                    billing_cycle=data['billing_cycle'],
                    status=TenantSubscription.Status.TRIAL,
                    trial_started_at=now,
                    trial_days=trial_days,
                    current_period_start=now,
                    current_period_end=now + timedelta(days=trial_days),
                    next_billing_date=now + timedelta(days=trial_days),
                )
    except Exception:
        logger.exception('Tenant registration failed for schema %s', data['schema_name'])
        return Response(
            {'error': 'Registration could not be completed. Please try again later.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    try:
        _send_verification_email(
            data['admin_email'], verification.token,
            data['schema_name'], scheme, base_domain,
        )
    except Exception:
        logger.exception(
            'Verification email failed for %s — tenant created, email not sent',
            data['admin_email'],
        )

    return Response(
        {
            'tenant': {
                'id': client.pk,
                'schema_name': client.schema_name,
                'name': client.name,
                'created_on': client.created_on,
            },
            'domain': full_domain,
            'admin_user': {
                'id': admin.pk,
                'email': admin.email,
                'username': admin.username,
                'role': admin.role,
                'is_active': admin.is_active,
            },
            'message': (
                f'Registration received. A verification email has been sent to '
                f'{data["admin_email"]}. Click the link to activate your account.'
            ),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def verify_tenant_email(request):
    """
    Consume an email-verification token, activate the admin user, and return JWT tokens.

    GET /api/tenants/verify-email/?token=<uuid>

    The frontend should store the tokens and redirect_url then navigate to
    the tenant's subdomain dashboard.
    """
    token_str = request.query_params.get('token', '')
    if not token_str:
        return Response({'error': 'Missing token.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        verification = TenantEmailVerification.objects.select_related('tenant').get(token=token_str)
    except (TenantEmailVerification.DoesNotExist, Exception):
        return Response(
            {'error': 'Invalid or expired verification link.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if verification.is_used:
        return Response(
            {'error': 'This verification link has already been used.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if verification.is_expired:
        return Response(
            {'error': 'This verification link has expired. Please register again.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        with schema_context(get_public_schema_name()):
            with transaction.atomic():
                admin = User.objects.get(email=verification.email, is_active=False)
                admin.is_active = True
                admin.save(update_fields=['is_active'])

                verification.used_at = timezone.now()
                verification.save(update_fields=['used_at'])
    except User.DoesNotExist:
        return Response(
            {'error': 'Account not found or already active.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception:
        logger.exception('Email verification failed for token %s', token_str)
        return Response(
            {'error': 'Verification could not be completed. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    refresh = RefreshToken.for_user(admin)
    base_domain = getattr(settings, 'TENANT_BASE_DOMAIN', 'localhost')
    scheme = _scheme_for(request)
    redirect_url = f"{scheme}://{verification.tenant.schema_name}.{base_domain}/dashboard"

    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'redirect_url': redirect_url,
        'tenant': {
            'schema_name': verification.tenant.schema_name,
            'name': verification.tenant.name,
        },
        'message': 'Email verified. Your account is now active.',
    })


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def resend_verification_email(request):
    """
    Resend verification email for admin who hasn't verified yet.
    """
    serializer = ResendVerificationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data['email']

    try:
        verification = TenantEmailVerification.objects.filter(
            email=email, used_at__isnull=True
        ).first()
        
        if not verification:
            # Check if already verified
            if User.objects.filter(email=email, is_active=True).exists():
                return Response(
                    {'error': 'This account is already verified.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            return Response(
                {'error': 'No pending verification found for this email.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update expiry
        verification.expires_at = timezone.now() + timedelta(hours=_VERIFICATION_EXPIRY_HOURS)
        verification.save(update_fields=['expires_at'])

        base_domain = getattr(settings, 'TENANT_BASE_DOMAIN', 'localhost')
        scheme = _scheme_for(request)
        
        _send_verification_email(
            email, verification.token,
            verification.tenant.schema_name, scheme, base_domain,
        )
        
        return Response({
            'status': 'success',
            'message': f'Verification email resent to {email}. Check your email.'
        })

    except Exception:
        logger.exception('Failed to resend verification email for %s', email)
        return Response(
            {'error': 'Could not resend verification email. Please try again later.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class SubscriptionPlanViewSet(viewsets.ModelViewSet):
    """
    Public pricing plans and Admin plan management.
    """
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanSerializer
    lookup_field = 'id'

    def get_permissions(self):
        if self.action == 'list':
            return [AllowAny()]
        return [IsAdminUser()]

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_active=True)
        return queryset


class TenantSubscriptionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    My subscription (Tenant admin) and all subscriptions (Global admin).
    """
    queryset = TenantSubscription.objects.all()
    serializer_class = TenantSubscriptionSerializer

    def get_permissions(self):
        if self.action in ['my_subscription', 'change_plan', 'invoices']:
            return [IsAuthenticated()]
        return [IsAdminUser()]

    @action(detail=False, methods=['get'], url_path='my-subscription')
    def my_subscription(self, request):
        """Current tenant's subscription."""
        # Note: request.tenant is set by TenantMainMiddleware
        tenant = getattr(request, 'tenant', None)
        if not tenant or tenant.schema_name == get_public_schema_name():
            return Response(
                {'error': 'Subscription not found for public schema.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            subscription = TenantSubscription.objects.get(tenant=tenant)
            serializer = self.get_serializer(subscription)
            return Response(serializer.data)
        except TenantSubscription.DoesNotExist:
            return Response(
                {'error': 'Subscription not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=['post'], url_path='my-subscription/change-plan')
    def change_plan(self, request):
        """Upgrade/downgrade subscription plan."""
        # Only admin/manager can change plan
        if not request.user.is_authenticated or request.user.role not in ['admin', 'manager']:
            return Response(
                {'error': 'Only administrators or managers can change plans.'},
                status=status.HTTP_403_FORBIDDEN
            )

        tenant = getattr(request, 'tenant', None)
        if not tenant or tenant.schema_name == get_public_schema_name():
            return Response({'error': 'Invalid tenant.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ChangePlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        plan_id = serializer.validated_data['plan_id']
        billing_cycle = serializer.validated_data['billing_cycle']
        
        try:
            subscription = TenantSubscription.objects.get(tenant=tenant)
            if not subscription.can_upgrade():
                return Response(
                    {'error': 'Subscription cannot be changed in its current status.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            new_plan = SubscriptionPlan.objects.get(id=plan_id)
            subscription.plan = new_plan
            subscription.billing_cycle = billing_cycle
            subscription.save()
            
            return Response({
                'status': 'success',
                'new_plan': new_plan.name,
                'billing_cycle': billing_cycle,
                'effective_date': timezone.now().date().isoformat()
            })
        except TenantSubscription.DoesNotExist:
            return Response({'error': 'Subscription not found.'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        """Admin: Suspend a subscription."""
        subscription = self.get_object()
        reason = request.data.get('reason', 'Administrative suspension')
        subscription.suspend(reason)
        return Response({
            'status': subscription.status,
            'reason': subscription.suspension_reason,
            'suspended_at': subscription.suspended_at
        })

    @action(detail=True, methods=['post'])
    def reactivate(self, request, pk=None):
        """Admin: Reactivate a subscription."""
        subscription = self.get_object()
        subscription.reactivate()
        return Response({'status': subscription.status})

    @action(detail=False, methods=['get'])
    def metrics(self, request):
        """Admin: SaaS metrics."""
        from django.db.models import Sum, Count
        active_subs = TenantSubscription.objects.filter(status=TenantSubscription.Status.ACTIVE)
        
        mrr = 0
        for sub in active_subs:
            if sub.billing_cycle == TenantSubscription.BillingCycle.MONTHLY:
                mrr += sub.plan.price_monthly
            else:
                mrr += sub.plan.price_annual / 12

        metrics = {
            'total_tenants': Client.objects.exclude(schema_name=get_public_schema_name()).count(),
            'active_subscriptions': active_subs.count(),
            'trialing': TenantSubscription.objects.filter(status=TenantSubscription.Status.TRIAL).count(),
            'suspended': TenantSubscription.objects.filter(status=TenantSubscription.Status.SUSPENDED).count(),
            'monthly_recurring_revenue': mrr,
            'annual_recurring_revenue': mrr * 12,
        }
        return Response(metrics)


class SubscriptionInvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    My invoices and Admin invoice view.
    """
    queryset = SubscriptionInvoice.objects.all()
    serializer_class = SubscriptionInvoiceSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve'] and (not self.request.user.is_authenticated or not self.request.user.is_staff):
            return [IsAuthenticated()]
        return [IsAdminUser()]

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            tenant = getattr(self.request, 'tenant', None)
            queryset = queryset.filter(subscription__tenant=tenant)
        return queryset
