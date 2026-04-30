from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes as perm_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.permissions import IsAdmin, IsAdminOrManager
from .models import SystemConfig, ApprovalThreshold, AuditSetting
from .serializers import (
    SystemConfigSerializer,
    ApprovalThresholdSerializer,
    AuditSettingSerializer,
    CheckApprovalSerializer,
)
from . import services


class SystemConfigViewSet(viewsets.ViewSet):
    """
    Tenant-level system configuration (singleton).
    GET to retrieve, PATCH to update.
    """
    permission_classes = [IsAuthenticated]

    def list(self, request):
        config = services.get_system_config()
        return Response(SystemConfigSerializer(config).data)

    def partial_update(self, request, pk=None):
        self.check_permissions(request)
        if not IsAdminOrManager().has_permission(request, self):
            return Response(
                {'error': 'Only admin or manager can update system configuration.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        config = services.get_system_config()
        serializer = SystemConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        config = services.update_system_config(serializer.validated_data)
        return Response(SystemConfigSerializer(config).data)

    @action(detail=False, methods=['post'], url_path='check-approval',
            permission_classes=[IsAdminOrManager])
    def check_approval(self, request):
        serializer = CheckApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        approved, required_role = services.check_approval(
            transaction_type=serializer.validated_data['transaction_type'],
            amount=serializer.validated_data['amount'],
            user_role=request.user.role,
        )
        return Response({
            'approved': approved,
            'required_role': required_role,
            'user_role': request.user.role,
        })


class ApprovalThresholdViewSet(viewsets.ModelViewSet):
    """CRUD for approval thresholds. Admin only for writes."""
    queryset = ApprovalThreshold.objects.all()
    serializer_class = ApprovalThresholdSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['transaction_type', 'requires_role', 'is_active']
    ordering_fields = ['min_amount', 'created_at']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdmin()]
        return [IsAuthenticated()]


class AuditSettingViewSet(viewsets.ModelViewSet):
    """CRUD for audit log settings. Admin only."""
    queryset = AuditSetting.objects.all()
    serializer_class = AuditSettingSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['log_type', 'is_enabled']
    permission_classes = [IsAdmin]
