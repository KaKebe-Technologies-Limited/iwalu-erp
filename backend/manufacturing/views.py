from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction, IntegrityError
from django.db.models import F
from django.utils import timezone
from decimal import Decimal, InvalidOperation
import logging

from .models import BillOfMaterials, ProductionOrder, WorkInProgress, ProductionOrderItem
from .serializers import (
    BillOfMaterialsSerializer, ProductionOrderSerializer,
    WorkInProgressSerializer, BOMCostBreakdownSerializer
)
from users.permissions import IsAdminOrManager, IsAccountantOrAbove
from inventory.models import OutletStock, StockAuditLog

logger = logging.getLogger(__name__)


class BillOfMaterialsViewSet(viewsets.ModelViewSet):
    queryset = BillOfMaterials.objects.select_related('finished_product').prefetch_related(
        'items', 'items__raw_material'
    ).all()
    serializer_class = BillOfMaterialsSerializer
    filterset_fields = ['is_active', 'finished_product']
    search_fields = ['name']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminOrManager()]
        if self.action == 'cost':
            return [IsAccountantOrAbove()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(created_by_id=self.request.user.id)

    @action(detail=True, methods=['get'])
    def cost(self, request, pk=None):
        bom = self.get_object()
        serializer = BOMCostBreakdownSerializer(bom)
        return Response(serializer.data)


class ProductionOrderViewSet(viewsets.ModelViewSet):
    queryset = ProductionOrder.objects.select_related(
        'bom', 'bom__finished_product', 'outlet'
    ).prefetch_related(
        'consumed_materials', 'consumed_materials__raw_material'
    ).all()
    serializer_class = ProductionOrderSerializer
    filterset_fields = ['status', 'bom', 'outlet']
    search_fields = ['order_number']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'start', 'complete', 'cancel']:
            return [IsAdminOrManager()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        today = timezone.now().strftime('%Y%m%d')
        for attempt in range(10):
            count = ProductionOrder.objects.filter(
                order_number__startswith=f"MFG-{today}"
            ).count() + 1 + attempt
            order_number = f"MFG-{today}-{count:04d}"
            try:
                serializer.save(
                    order_number=order_number,
                    ordered_by_id=self.request.user.id
                )
                return
            except IntegrityError:
                if attempt == 9:
                    raise
                continue

    def update(self, request, *args, **kwargs):
        order = self.get_object()
        if order.status in (ProductionOrder.Status.COMPLETED, ProductionOrder.Status.CANCELLED):
            return Response(
                {"error": "Cannot modify a completed or cancelled order."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        order = self.get_object()
        if order.status != ProductionOrder.Status.DRAFT:
            return Response(
                {"error": "Only draft orders can be deleted."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        order = self.get_object()
        if order.status != ProductionOrder.Status.DRAFT:
            return Response(
                {"error": f"Cannot start order in {order.status} status."},
                status=status.HTTP_400_BAD_REQUEST
            )

        order.status = ProductionOrder.Status.IN_PROGRESS
        order.actual_start = timezone.now()
        order.save()
        return Response({
            "status": order.status,
            "actual_start": order.actual_start
        })

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        order = self.get_object()
        if order.status in (ProductionOrder.Status.COMPLETED, ProductionOrder.Status.CANCELLED):
            return Response(
                {"error": f"Cannot cancel order in {order.status} status."},
                status=status.HTTP_400_BAD_REQUEST
            )
        order.status = ProductionOrder.Status.CANCELLED
        order.save()
        return Response(ProductionOrderSerializer(order).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        order = self.get_object()
        if order.status != ProductionOrder.Status.IN_PROGRESS:
            return Response(
                {"error": f"Cannot complete order in {order.status} status."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            quantity_produced = Decimal(str(request.data.get('quantity_produced', order.quantity_to_produce)))
        except (InvalidOperation, TypeError, ValueError):
            return Response({"error": "Invalid quantity_produced value."}, status=status.HTTP_400_BAD_REQUEST)
        if quantity_produced <= Decimal('0'):
            return Response({"error": "quantity_produced must be positive."}, status=status.HTTP_400_BAD_REQUEST)

        notes = request.data.get('notes', order.notes)

        with transaction.atomic():
            bom = order.bom
            required_materials = order.get_required_materials()

            shortages = []
            stocks_to_update = {}

            for m in required_materials:
                stock, created = OutletStock.objects.select_for_update().get_or_create(
                    outlet=order.outlet,
                    product=m['raw_material'],
                    defaults={'quantity': Decimal('0')}
                )

                if stock.quantity < m['quantity_needed']:
                    shortages.append({
                        'product': m['raw_material'].name,
                        'required': str(m['quantity_needed']),
                        'available': str(stock.quantity)
                    })
                stocks_to_update[stock.id] = (stock, m['quantity_needed'])

            if shortages:
                return Response(
                    {"error": "Insufficient raw material stock", "shortages": shortages},
                    status=status.HTTP_400_BAD_REQUEST
                )

            total_material_cost = Decimal('0')
            for stock_id, (stock, needed) in stocks_to_update.items():
                qty_before = stock.quantity
                qty_after = qty_before - needed

                OutletStock.objects.filter(id=stock_id).update(quantity=qty_after)

                StockAuditLog.objects.create(
                    product=stock.product,
                    outlet=order.outlet,
                    movement_type='adjustment',
                    quantity_change=-needed,
                    quantity_before=qty_before,
                    quantity_after=qty_after,
                    reference_type='manufacturing_order',
                    reference_id=order.id,
                    notes=f"Consumption for production {order.order_number}",
                    user_id=request.user.id
                )

                unit_cost = stock.product.cost_price or Decimal('0')
                line_cost = (needed * unit_cost).quantize(Decimal('0.01'))
                total_material_cost += line_cost

                ProductionOrderItem.objects.create(
                    production_order=order,
                    raw_material=stock.product,
                    quantity_planned=needed,
                    quantity_actual=needed,
                    unit=stock.product.unit or 'unit',
                    unit_cost=unit_cost,
                    line_cost=line_cost
                )

            finished_stock, created = OutletStock.objects.select_for_update().get_or_create(
                outlet=order.outlet,
                product=bom.finished_product,
                defaults={'quantity': Decimal('0')}
            )

            qty_before_fp = finished_stock.quantity
            qty_after_fp = qty_before_fp + quantity_produced

            OutletStock.objects.filter(id=finished_stock.id).update(quantity=qty_after_fp)

            StockAuditLog.objects.create(
                product=bom.finished_product,
                outlet=order.outlet,
                movement_type='adjustment',
                quantity_change=quantity_produced,
                quantity_before=qty_before_fp,
                quantity_after=qty_after_fp,
                reference_type='manufacturing_order',
                reference_id=order.id,
                notes=f"Production output from {order.order_number}",
                user_id=request.user.id
            )

            order.status = ProductionOrder.Status.COMPLETED
            order.completed_at = timezone.now()
            order.quantity_produced = quantity_produced
            order.total_material_cost = total_material_cost
            order.notes = notes
            order.save()

        return Response(ProductionOrderSerializer(order).data)


class WorkInProgressViewSet(viewsets.ModelViewSet):
    queryset = WorkInProgress.objects.select_related('production_order').all()
    serializer_class = WorkInProgressSerializer
    filterset_fields = ['production_order']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminOrManager()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(recorded_by_id=self.request.user.id)
