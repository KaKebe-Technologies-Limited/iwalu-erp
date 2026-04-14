from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.permissions import IsAdmin, IsAdminOrManager
from .models import EfrisConfig, FiscalInvoice
from .serializers import EfrisConfigSerializer, FiscalInvoiceSerializer
from . import services


class EfrisConfigViewSet(viewsets.ViewSet):
    """
    Tenant-level EFRIS configuration singleton.
    GET to retrieve, PATCH to update (admin only).
    """
    permission_classes = [IsAuthenticated]

    def list(self, request):
        config = services.get_config()
        return Response(EfrisConfigSerializer(config).data)

    def partial_update(self, request, pk=None):
        if not IsAdmin().has_permission(request, self):
            return Response(
                {'error': 'Only admin can update EFRIS configuration.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        config = services.get_config()
        serializer = EfrisConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(EfrisConfigSerializer(config).data)

    @action(detail=False, methods=['post'], url_path='test-connection',
            permission_classes=[IsAdmin])
    def test_connection(self, request):
        """Run the configured provider's health_check()."""
        try:
            provider = services.get_provider()
            ok = provider.health_check()
            return Response({
                'provider': provider.name,
                'healthy': bool(ok),
            })
        except Exception as exc:
            return Response(
                {'error': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class FiscalInvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only view of fiscal invoice submissions. Admin/manager can see all;
    staff can view but not modify. Use the retry action to re-submit failures.
    """
    queryset = FiscalInvoice.objects.select_related('sale').all()
    serializer_class = FiscalInvoiceSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'provider']
    search_fields = ['fdn', 'invoice_id', 'sale__receipt_number']
    ordering_fields = ['created_at', 'submitted_at', 'retry_count']

    def get_permissions(self):
        if self.action in ('retry',):
            return [IsAdminOrManager()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """Manually retry a single failed fiscal invoice."""
        fiscal_invoice = self.get_object()
        if fiscal_invoice.status != 'failed':
            return Response(
                {'error': f'Only failed invoices can be retried '
                          f'(current: {fiscal_invoice.status}).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            provider = services.get_provider()
            result = provider.submit_invoice(fiscal_invoice.request_payload)
        except Exception as exc:
            fiscal_invoice.retry_count += 1
            fiscal_invoice.error_message = str(exc)[:2000]
            fiscal_invoice.save()
            return Response(
                {'error': str(exc), 'retry_count': fiscal_invoice.retry_count},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.utils import timezone
        fiscal_invoice.status = 'accepted' if result.success else 'rejected'
        fiscal_invoice.retry_count += 1
        fiscal_invoice.fdn = result.fdn
        fiscal_invoice.invoice_id = result.invoice_id
        fiscal_invoice.verification_code = result.verification_code
        fiscal_invoice.qr_code = result.qr_code
        fiscal_invoice.response_payload = result.raw_response
        fiscal_invoice.accepted_at = timezone.now()
        fiscal_invoice.error_message = ''
        fiscal_invoice.save()
        return Response(FiscalInvoiceSerializer(fiscal_invoice).data)

    @action(detail=False, methods=['post'], url_path='retry-all',
            permission_classes=[IsAdminOrManager])
    def retry_all(self, request):
        """Retry all failed invoices up to MAX_RETRY_ATTEMPTS."""
        stats = services.retry_failed_invoices()
        return Response(stats)
