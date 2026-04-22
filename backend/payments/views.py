"""
Payments views.

ViewSets:
    PaymentConfigViewSet — manage tenant-level provider credentials (admin only).
    PaymentTransactionViewSet — read-only audit trail; row-level scoped for
                                non-privileged roles.

Action Views:
    PaymentViewSet — initiate collections/disbursements and handle provider
                     callbacks. The callback endpoint is intentionally
                     unauthenticated (webhooks) but every payload is
                     re-verified against the provider before any state change.
"""
import logging
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, permissions, decorators
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from drf_spectacular.utils import extend_schema, extend_schema_view

from users.permissions import IsAdmin, IsAdminOrManager
from .models import PaymentConfig, PaymentTransaction
from .serializers import (
    PaymentConfigSerializer, PaymentTransactionSerializer,
    InitiatePaymentSerializer, InitiateDisbursementSerializer,
)
from .services import (
    initiate_payment, initiate_disbursement,
    handle_callback, query_payment_status, get_config
)

logger = logging.getLogger(__name__)


def _redact_phone(phone: str) -> str:
    """Mask all but the last 4 digits of a phone number for logs."""
    if not phone:
        return ''
    digits = ''.join(c for c in str(phone) if c.isdigit())
    if len(digits) <= 4:
        return '***'
    return f'***{digits[-4:]}'


class CallbackThrottle(AnonRateThrottle):
    """Per-IP throttle for the public webhook endpoint."""
    scope = 'payment-callback'


class PaymentConfigViewSet(viewsets.ModelViewSet):
    """
    Manage tenant-level payment provider configurations. Admin only — these
    fields hold collection AND disbursement credentials, so a compromise
    means money out the door.
    """
    queryset = PaymentConfig.objects.all()
    serializer_class = PaymentConfigSerializer
    permission_classes = [IsAdmin]

    def get_object(self):
        return get_config()

    @extend_schema(description="Get the payment configuration for the current tenant.")
    def list(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(description="List payment transactions (audit trail)."),
    retrieve=extend_schema(description="Retrieve a specific payment transaction."),
)
class PaymentTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Audit trail of payment attempts.

    Admin/manager see all transactions; everyone else only sees transactions
    they personally initiated. Row-level scoping prevents IDOR-style
    enumeration of other cashiers' customer phone numbers / emails.
    """
    queryset = PaymentTransaction.objects.all()
    serializer_class = PaymentTransactionSerializer
    filterset_fields = ['status', 'provider', 'method', 'sale', 'transaction_type']
    search_fields = ['reference', 'provider_transaction_id', 'phone_number', 'customer_email']

    def get_permissions(self):
        if self.action == 'refresh_status':
            return [IsAdminOrManager()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()
        if user.role in ('admin', 'manager'):
            return qs
        return qs.filter(initiated_by=user.pk)

    @decorators.action(detail=True, methods=['post'])
    def refresh_status(self, request, pk=None):
        """Force a poll of the provider to get the latest status."""
        txn = self.get_object()
        updated_txn = query_payment_status(txn)
        serializer = self.get_serializer(updated_txn)
        return Response(serializer.data)


class PaymentViewSet(viewsets.GenericViewSet):
    """
    Functional endpoints for initiating payments and handling callbacks.
    """
    queryset = PaymentTransaction.objects.none()
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request=InitiatePaymentSerializer,
        responses={201: PaymentTransactionSerializer},
        description="Initiate a new payment (collection) via a provider."
    )
    @decorators.action(detail=False, methods=['post'], url_path='initiate')
    def initiate(self, request):
        serializer = InitiatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        sale_id = serializer.validated_data.get('sale_id')
        sale = None
        if sale_id:
            from sales.models import Sale
            sale = get_object_or_404(Sale, id=sale_id)

        txn = initiate_payment(
            amount=serializer.validated_data['amount'],
            method=serializer.validated_data['method'],
            provider_name=serializer.validated_data.get('provider'),
            phone_number=serializer.validated_data.get('phone_number', ''),
            customer_email=serializer.validated_data.get('customer_email', ''),
            customer_name=serializer.validated_data.get('customer_name', ''),
            description=serializer.validated_data.get('description', ''),
            sale=sale,
            currency=serializer.validated_data.get('currency'),
            initiated_by_id=request.user.id,
        )

        return Response(
            PaymentTransactionSerializer(txn).data,
            status=status.HTTP_201_CREATED if txn.status != 'failed' else status.HTTP_400_BAD_REQUEST
        )

    @extend_schema(
        request=InitiateDisbursementSerializer,
        responses={201: PaymentTransactionSerializer},
        description="Initiate a new disbursement (send money) via a provider."
    )
    @decorators.action(
        detail=False, methods=['post'], url_path='disburse',
        permission_classes=[IsAdminOrManager],
    )
    def disburse(self, request):
        serializer = InitiateDisbursementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        txn = initiate_disbursement(
            amount=serializer.validated_data['amount'],
            method=serializer.validated_data['method'],
            provider_name=serializer.validated_data.get('provider'),
            phone_number=serializer.validated_data.get('phone_number', ''),
            customer_email=serializer.validated_data.get('customer_email', ''),
            customer_name=serializer.validated_data.get('customer_name', ''),
            description=serializer.validated_data.get('description', ''),
            currency=serializer.validated_data.get('currency'),
            initiated_by_id=request.user.id,
        )

        return Response(
            PaymentTransactionSerializer(txn).data,
            status=status.HTTP_201_CREATED if txn.status != 'failed' else status.HTTP_400_BAD_REQUEST
        )

    @extend_schema(exclude=True)
    @decorators.action(
        detail=False, methods=['post', 'get'],
        url_path='callback/(?P<provider_name>[^/.]+)',
        permission_classes=[permissions.AllowAny],
        throttle_classes=[CallbackThrottle],
    )
    def callback(self, request, provider_name=None):
        """
        Public webhook endpoint for providers.

        Security model: we DO NOT trust the payload. Whatever the caller posts
        is treated as a notification "something happened" — `handle_callback`
        re-queries the provider for the authoritative status before any
        money-affecting state change. We additionally drop callbacks for
        already-terminal transactions (replay protection) and refuse to log
        the raw payload (PII).
        """
        payload = request.data if request.method == 'POST' else request.query_params.dict()
        # Redact: log only the provider name + a phone-tail / reference if
        # present. Never the full payload (contains MSISDN, email, signatures).
        ref = payload.get('externalId') or payload.get('OrderMerchantReference') or ''
        logger.info(
            'callback provider=%s ref=%s phone=%s',
            provider_name, ref, _redact_phone(payload.get('phoneNumber', '')),
        )

        txn = handle_callback(provider_name, payload, request=request)
        if txn:
            return Response({'status': 'ok'})
        return Response({'status': 'ignored'}, status=status.HTTP_404_NOT_FOUND)
