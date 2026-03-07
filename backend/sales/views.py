from decimal import Decimal
from django.db import models
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.permissions import IsAdminOrManager, IsCashierOrAbove
from .models import Discount, Shift, Sale, Payment
from .serializers import (
    DiscountSerializer, ShiftSerializer, OpenShiftSerializer,
    CloseShiftSerializer, SaleSerializer, SaleListSerializer,
    CheckoutSerializer,
)
from .services import process_checkout


class DiscountViewSet(viewsets.ModelViewSet):
    queryset = Discount.objects.all()
    serializer_class = DiscountSerializer
    search_fields = ['name']
    filterset_fields = ['discount_type', 'is_active']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminOrManager()]
        return [IsAuthenticated()]


class ShiftViewSet(viewsets.GenericViewSet):
    queryset = Shift.objects.all()
    serializer_class = ShiftSerializer
    filterset_fields = ['outlet', 'status']

    def get_permissions(self):
        return [IsCashierOrAbove()]

    def list(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='open')
    def open_shift(self, request):
        serializer = OpenShiftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Check for existing open shift
        existing = Shift.objects.filter(
            user_id=request.user.id, status='open',
        ).first()
        if existing:
            return Response(
                {'error': 'You already have an open shift.',
                 'shift_id': existing.pk},
                status=status.HTTP_400_BAD_REQUEST,
            )

        shift = Shift.objects.create(
            outlet_id=serializer.validated_data['outlet'],
            user_id=request.user.id,
            opening_cash=serializer.validated_data['opening_cash'],
        )
        return Response(ShiftSerializer(shift).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='close')
    def close_shift(self, request, pk=None):
        shift = self.get_object()
        if shift.status == 'closed':
            return Response(
                {'error': 'Shift is already closed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = CloseShiftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Calculate expected cash: opening_cash + cash payments during shift
        cash_payments = (
            Payment.objects
            .filter(sale__shift=shift, payment_method='cash')
            .aggregate(total=models.Sum('amount'))
        )
        cash_total = cash_payments['total'] or Decimal('0.00')
        expected_cash = shift.opening_cash + cash_total

        shift.closing_cash = serializer.validated_data['closing_cash']
        shift.expected_cash = expected_cash
        shift.notes = serializer.validated_data.get('notes', '')
        shift.status = 'closed'
        shift.closed_at = timezone.now()
        shift.save()

        return Response(ShiftSerializer(shift).data)

    @action(detail=False, methods=['get'], url_path='my_current')
    def my_current(self, request):
        shift = Shift.objects.filter(
            user_id=request.user.id, status='open',
        ).first()
        if not shift:
            return Response(
                {'error': 'No open shift found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(ShiftSerializer(shift).data)


class SaleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Sale.objects.all()
    search_fields = ['receipt_number']
    filterset_fields = ['outlet', 'status', 'shift']
    ordering_fields = ['created_at', 'grand_total']

    def get_permissions(self):
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == 'list':
            return SaleListSerializer
        return SaleSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == 'retrieve':
            qs = qs.prefetch_related('items', 'payments')
        return qs

    @action(detail=True, methods=['post'])
    def void(self, request, pk=None):
        self.permission_classes = [IsAdminOrManager]
        self.check_permissions(request)

        sale = self.get_object()
        if sale.status == 'voided':
            return Response(
                {'error': 'Sale is already voided.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Restore stock
        for item in sale.items.select_related('product').all():
            product = item.product
            if product.track_stock:
                product.stock_quantity += item.quantity
                product.save(update_fields=['stock_quantity', 'updated_at'])

        sale.status = 'voided'
        sale.save(update_fields=['status', 'updated_at'])
        return Response(SaleSerializer(sale).data)

    @action(detail=True, methods=['get'])
    def receipt(self, request, pk=None):
        sale = self.get_object()
        serializer = SaleSerializer(sale)
        return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsCashierOrAbove])
def checkout(request):
    serializer = CheckoutSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    # Get current user's open shift
    shift = Shift.objects.filter(
        user_id=request.user.id, status='open',
    ).first()
    if not shift:
        return Response(
            {'error': 'You must have an open shift to process a sale.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    sale = process_checkout(
        shift=shift,
        cashier_id=request.user.id,
        items_data=serializer.validated_data['items'],
        payments_data=serializer.validated_data['payments'],
        discount_id=serializer.validated_data.get('discount_id'),
        notes=serializer.validated_data.get('notes', ''),
    )

    return Response(SaleSerializer(sale).data, status=status.HTTP_201_CREATED)
