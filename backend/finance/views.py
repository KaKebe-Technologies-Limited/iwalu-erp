from datetime import date

from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.permissions import IsAdminOrManager, IsAccountantOrAbove
from .models import Account, FiscalPeriod, JournalEntry, CashRequisition
from .serializers import (
    AccountSerializer, AccountCreateSerializer,
    FiscalPeriodSerializer,
    JournalEntrySerializer, JournalEntryCreateSerializer,
    CashRequisitionSerializer,
)
from . import services
from approvals.models import ApprovalPolicy, ApprovalRequest
from notifications.services import notify_approval_required


class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.select_related('parent', 'outlet').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['code', 'name']
    ordering_fields = ['code', 'name', 'account_type']

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return AccountCreateSerializer
        return AccountSerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAccountantOrAbove()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        account_type = self.request.query_params.get('account_type')
        if account_type:
            qs = qs.filter(account_type=account_type)
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == 'true')
        root = self.request.query_params.get('root')
        if root and root.lower() == 'true':
            qs = qs.filter(parent__isnull=True)
        return qs

    def destroy(self, request, *args, **kwargs):
        account = self.get_object()
        if account.is_system:
            return Response(
                {'error': 'Cannot delete a system account.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if account.journal_lines.exists():
            return Response(
                {'error': 'Cannot delete account with journal entries.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)


class FiscalPeriodViewSet(viewsets.ModelViewSet):
    queryset = FiscalPeriod.objects.all()
    serializer_class = FiscalPeriodSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy', 'close'):
            return [IsAccountantOrAbove()]
        return [IsAuthenticated()]

    def update(self, request, *args, **kwargs):
        period = self.get_object()
        if period.is_closed:
            return Response(
                {'error': 'Cannot modify a closed fiscal period.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        period = self.get_object()
        if period.is_closed:
            return Response(
                {'error': 'Cannot delete a closed fiscal period.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        period = self.get_object()
        if period.is_closed:
            return Response(
                {'error': 'Period is already closed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        period.is_closed = True
        period.closed_by = request.user.pk
        period.closed_at = timezone.now()
        period.save(update_fields=['is_closed', 'closed_by', 'closed_at', 'updated_at'])
        return Response(FiscalPeriodSerializer(period).data)


class JournalEntryViewSet(viewsets.ModelViewSet):
    queryset = (
        JournalEntry.objects
        .select_related('fiscal_period')
        .prefetch_related('lines__account')
        .all()
    )
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['entry_number', 'description']
    ordering_fields = ['date', 'entry_number', 'created_at']

    def get_serializer_class(self):
        if self.action == 'create':
            return JournalEntryCreateSerializer
        return JournalEntrySerializer

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy', 'post_entry', 'void_entry'):
            return [IsAccountantOrAbove()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        source = self.request.query_params.get('source')
        if source:
            qs = qs.filter(source=source)
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = services.create_journal_entry(
            date=serializer.validated_data['date'],
            description=serializer.validated_data['description'],
            lines_data=[dict(l) for l in serializer.validated_data['lines']],
            created_by=request.user.pk,
        )
        return Response(
            JournalEntrySerializer(entry).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        entry = self.get_object()
        if entry.status != 'draft':
            return Response(
                {'error': 'Only draft entries can be edited.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        entry = self.get_object()
        if entry.status != 'draft':
            return Response(
                {'error': 'Only draft entries can be deleted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='post')
    def post_entry(self, request, pk=None):
        entry = self.get_object()
        services.post_journal_entry(entry, request.user.pk)
        return Response(JournalEntrySerializer(entry).data)

    @action(detail=True, methods=['post'], url_path='void')
    def void_entry(self, request, pk=None):
        entry = self.get_object()
        reversal = services.void_journal_entry(entry, request.user.pk)
        return Response({
            'voided_entry': JournalEntrySerializer(entry).data,
            'reversal_entry': JournalEntrySerializer(reversal).data,
        })


class CashRequisitionViewSet(viewsets.ModelViewSet):
    queryset = CashRequisition.objects.all()
    serializer_class = CashRequisitionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'requisition_type']

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.role not in ('admin', 'manager', 'accountant'):
            qs = qs.filter(requested_by_id=self.request.user.pk)
        return qs

    def create(self, request, *args, **kwargs):
        from django.db import transaction
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            requisition = serializer.save(
                requested_by_id=request.user.pk,
                requisition_number=services.generate_requisition_number(),
                status='pending'
            )
            
            # Create approval
            policy = ApprovalPolicy.objects.filter(
                resource_type=ApprovalPolicy.ResourceType.CASH_REQUISITION,
                is_active=True
            ).order_by('min_amount').filter(
                models.Q(min_amount__lte=requisition.amount) | models.Q(min_amount__isnull=True)
            ).last()
            
            if policy:
                approval = ApprovalRequest.objects.create(
                    policy=policy,
                    resource_type=ApprovalPolicy.ResourceType.CASH_REQUISITION,
                    resource_id=requisition.id,
                    requested_by_id=request.user.pk,
                    amount=requisition.amount,
                    approval_chain_state=policy.approval_levels,
                    notes=requisition.purpose
                )
                requisition.approval_request = approval
                requisition.save(update_fields=['approval_request'])
                
                # Notify
                approver_ids = approval.get_approvers_at_level(1)
                notify_approval_required(
                    transaction_type="Cash Requisition",
                    amount=requisition.amount,
                    requester_name=request.user.get_full_name() or request.user.username,
                    reference_id=approval.id,
                    recipient_ids=approver_ids
                )
            else:
                # No policy, auto-approve
                requisition.status = 'approved'
                requisition.save(update_fields=['status'])
                
        return Response(
            CashRequisitionSerializer(requisition).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAccountantOrAbove])
    def pay(self, request, pk=None):
        requisition = self.get_object()
        if requisition.status != 'approved':
            return Response(
                {'error': f'Cannot pay a {requisition.status} requisition.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        requisition.status = 'paid'
        requisition.paid_by_id = request.user.pk
        requisition.paid_at = timezone.now()
        requisition.save()
        return Response(CashRequisitionSerializer(requisition).data)


# --- Financial report views ---

def _parse_date(value):
    """Parse a date string, returning None on invalid input."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return 'invalid'


@api_view(['GET'])
@permission_classes([IsAccountantOrAbove])
def trial_balance_view(request):
    as_of_date = _parse_date(request.query_params.get('as_of_date'))
    if as_of_date == 'invalid':
        return Response(
            {'error': 'Invalid date format. Use YYYY-MM-DD.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    outlet = request.query_params.get('outlet')
    data = services.get_trial_balance(as_of_date=as_of_date, outlet=outlet)
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAccountantOrAbove])
def profit_loss_view(request):
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    if not date_from or not date_to:
        return Response(
            {'error': 'date_from and date_to are required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    parsed_from = _parse_date(date_from)
    parsed_to = _parse_date(date_to)
    if parsed_from == 'invalid' or parsed_to == 'invalid':
        return Response(
            {'error': 'Invalid date format. Use YYYY-MM-DD.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    outlet = request.query_params.get('outlet')
    data = services.get_profit_and_loss(
        date_from=date_from, date_to=date_to, outlet=outlet,
    )
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAccountantOrAbove])
def balance_sheet_view(request):
    as_of_date = _parse_date(request.query_params.get('as_of_date'))
    if as_of_date == 'invalid':
        return Response(
            {'error': 'Invalid date format. Use YYYY-MM-DD.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    outlet = request.query_params.get('outlet')
    data = services.get_balance_sheet(as_of_date=as_of_date, outlet=outlet)
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAccountantOrAbove])
def account_ledger_view(request, pk):
    from django.shortcuts import get_object_or_404
    get_object_or_404(Account, pk=pk)
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    data = services.get_account_ledger(
        account_id=pk, date_from=date_from, date_to=date_to,
    )
    return Response(data)
