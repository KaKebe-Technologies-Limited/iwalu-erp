from decimal import Decimal
from django.db import models
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from outlets.models import Outlet
from products.models import Product
from users.permissions import IsAdminOrManager
from .models import (
    Supplier, OutletStock, PurchaseOrder, PurchaseOrderItem,
    StockTransfer, StockTransferItem, StockAuditLog,
)
from .serializers import (
    SupplierSerializer, OutletStockSerializer,
    PurchaseOrderSerializer, PurchaseOrderCreateSerializer,
    ReceivePurchaseOrderSerializer,
    StockTransferSerializer, StockTransferCreateSerializer,
    ReceiveTransferSerializer,
    StockAuditLogSerializer,
)
from .services import (
    generate_po_number, receive_purchase_order,
    generate_transfer_number, dispatch_transfer, receive_transfer,
)


class SupplierViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    search_fields = ['name', 'contact_person', 'email']
    filterset_fields = ['is_active']
    ordering_fields = ['name', 'created_at']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminOrManager()]
        return [IsAuthenticated()]


class OutletStockViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = OutletStock.objects.select_related('product', 'outlet').all()
    serializer_class = OutletStockSerializer
    filterset_fields = ['outlet', 'product']
    ordering_fields = ['quantity', 'updated_at']
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def low(self, request):
        queryset = (
            OutletStock.objects
            .select_related('product', 'outlet')
            .filter(
                product__track_stock=True,
                product__is_active=True,
                quantity__lte=models.F('product__reorder_level'),
            )
        )
        outlet_id = request.query_params.get('outlet')
        if outlet_id:
            queryset = queryset.filter(outlet_id=outlet_id)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = PurchaseOrder.objects.select_related('supplier', 'outlet').prefetch_related('items__product').all()
    serializer_class = PurchaseOrderSerializer
    search_fields = ['po_number', 'supplier__name']
    filterset_fields = ['supplier', 'outlet', 'status']
    ordering_fields = ['created_at', 'total_cost']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy',
                           'submit', 'receive', 'cancel'):
            return [IsAdminOrManager()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        from django.db import transaction

        serializer = PurchaseOrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Validate references
        try:
            Supplier.objects.get(pk=data['supplier_id'], is_active=True)
        except Supplier.DoesNotExist:
            return Response(
                {'supplier_id': 'Supplier not found or inactive.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            Outlet.objects.get(pk=data['outlet_id'])
        except Outlet.DoesNotExist:
            return Response(
                {'outlet_id': 'Outlet not found.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate all products exist before creating anything
        for item_data in data['items']:
            try:
                Product.objects.get(pk=item_data['product_id'], is_active=True)
            except Product.DoesNotExist:
                return Response(
                    {'items': f'Product {item_data["product_id"]} not found or inactive.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        with transaction.atomic():
            total_cost = Decimal('0.00')
            po = PurchaseOrder.objects.create(
                po_number=generate_po_number(),
                supplier_id=data['supplier_id'],
                outlet_id=data['outlet_id'],
                ordered_by=request.user.id,
                expected_date=data.get('expected_date'),
                notes=data.get('notes', ''),
            )

            for item_data in data['items']:
                qty = item_data['quantity_ordered']
                cost = item_data['unit_cost']
                line_total = (qty * cost).quantize(Decimal('0.01'))
                total_cost += line_total
                PurchaseOrderItem.objects.create(
                    purchase_order=po,
                    product_id=item_data['product_id'],
                    quantity_ordered=qty,
                    unit_cost=cost,
                    line_total=line_total,
                )

            po.total_cost = total_cost
            po.save(update_fields=['total_cost'])

        po.refresh_from_db()
        return Response(
            PurchaseOrderSerializer(po).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status != 'draft':
            return Response(
                {'error': 'Can only edit draft purchase orders.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status != 'draft':
            return Response(
                {'error': 'Can only delete draft purchase orders.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        po = self.get_object()
        if po.status != 'draft':
            return Response(
                {'error': f'Cannot submit a {po.status} purchase order.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        po.status = 'submitted'
        po.save(update_fields=['status', 'updated_at'])
        return Response(PurchaseOrderSerializer(po).data)

    @action(detail=True, methods=['post'])
    def receive(self, request, pk=None):
        po = self.get_object()
        serializer = ReceivePurchaseOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        po = receive_purchase_order(
            po, serializer.validated_data['items'], request.user.id,
        )
        return Response(PurchaseOrderSerializer(po).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        po = self.get_object()
        if po.status in ('received', 'cancelled'):
            return Response(
                {'error': f'Cannot cancel a {po.status} purchase order.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        po.status = 'cancelled'
        po.save(update_fields=['status', 'updated_at'])
        return Response(PurchaseOrderSerializer(po).data)


class StockTransferViewSet(viewsets.ModelViewSet):
    queryset = StockTransfer.objects.select_related('from_outlet', 'to_outlet').prefetch_related('items__product').all()
    serializer_class = StockTransferSerializer
    search_fields = ['transfer_number']
    filterset_fields = ['from_outlet', 'to_outlet', 'status']
    ordering_fields = ['created_at']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy',
                           'dispatch', 'receive', 'cancel'):
            return [IsAdminOrManager()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        from django.db import transaction

        serializer = StockTransferCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Validate outlets
        for field, label in [('from_outlet_id', 'Source'), ('to_outlet_id', 'Destination')]:
            try:
                Outlet.objects.get(pk=data[field])
            except Outlet.DoesNotExist:
                return Response(
                    {field: f'{label} outlet not found.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Validate all products exist before creating anything
        for item_data in data['items']:
            try:
                Product.objects.get(pk=item_data['product_id'], is_active=True)
            except Product.DoesNotExist:
                return Response(
                    {'items': f'Product {item_data["product_id"]} not found or inactive.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        with transaction.atomic():
            transfer = StockTransfer.objects.create(
                transfer_number=generate_transfer_number(),
                from_outlet_id=data['from_outlet_id'],
                to_outlet_id=data['to_outlet_id'],
                initiated_by=request.user.id,
                notes=data.get('notes', ''),
            )

            for item_data in data['items']:
                StockTransferItem.objects.create(
                    transfer=transfer,
                    product_id=item_data['product_id'],
                    quantity=item_data['quantity'],
                )

        transfer.refresh_from_db()
        return Response(
            StockTransferSerializer(transfer).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status != 'pending':
            return Response(
                {'error': 'Can only edit pending transfers.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status != 'pending':
            return Response(
                {'error': 'Can only delete pending transfers.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def dispatch(self, request, pk=None):
        transfer = self.get_object()
        transfer = dispatch_transfer(transfer, request.user.id)
        return Response(StockTransferSerializer(transfer).data)

    @action(detail=True, methods=['post'])
    def receive(self, request, pk=None):
        transfer = self.get_object()
        serializer = ReceiveTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        transfer = receive_transfer(
            transfer, serializer.validated_data['items'], request.user.id,
        )
        return Response(StockTransferSerializer(transfer).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        transfer = self.get_object()
        if transfer.status not in ('pending',):
            return Response(
                {'error': f'Cannot cancel a {transfer.status} transfer.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        transfer.status = 'cancelled'
        transfer.save(update_fields=['status', 'updated_at'])
        return Response(StockTransferSerializer(transfer).data)


class StockAuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StockAuditLog.objects.select_related('product', 'outlet').all()
    serializer_class = StockAuditLogSerializer
    filterset_fields = ['product', 'outlet', 'movement_type']
    ordering_fields = ['created_at']
    permission_classes = [IsAuthenticated]
