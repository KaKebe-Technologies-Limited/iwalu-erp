from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from decimal import Decimal

from .models import BillOfMaterials, ProductionOrder, WorkInProgress, ProductionOrderItem
from .serializers import (
    BillOfMaterialsSerializer, ProductionOrderSerializer, 
    WorkInProgressSerializer, BOMCostBreakdownSerializer
)
from users.permissions import IsAdminOrManager, IsAccountantOrAbove
from inventory.models import OutletStock, StockAuditLog


class BillOfMaterialsViewSet(viewsets.ModelViewSet):
    queryset = BillOfMaterials.objects.all()
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
        bom = self.get_object_or_404(BillOfMaterials.objects.select_related('finished_product'), pk=pk)
        serializer = BOMCostBreakdownSerializer(bom)
        return Response(serializer.data)

    def get_object_or_404(self, queryset, **kwargs):
        return get_object_or_404(queryset, **kwargs)


class ProductionOrderViewSet(viewsets.ModelViewSet):
    queryset = ProductionOrder.objects.all()
    serializer_class = ProductionOrderSerializer
    filterset_fields = ['status', 'bom', 'outlet']
    search_fields = ['order_number']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'start', 'complete']:
            return [IsAdminOrManager()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        # Auto-generate order number: MFG-YYYYMMDD-XXXX
        today = timezone.now().strftime('%Y%m%d')
        count = ProductionOrder.objects.filter(order_number__contains=today).count() + 1
        order_number = f"MFG-{today}-{count:04d}"
        serializer.save(
            order_number=order_number,
            ordered_by_id=self.request.user.id
        )

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
    def complete(self, request, pk=None):
        order = self.get_object()
        if order.status != ProductionOrder.Status.IN_PROGRESS:
            return Response(
                {"error": f"Cannot complete order in {order.status} status."},
                status=status.HTTP_400_BAD_REQUEST
            )

        quantity_produced = Decimal(request.data.get('quantity_produced', order.quantity_to_produce))
        notes = request.data.get('notes', order.notes)

        try:
            with transaction.atomic():
                # Step 1: Pre-flight check & select_for_update
                bom = order.bom
                required_materials = order.get_required_materials()
                
                shortages = []
                stocks_to_update = {}
                
                for m in required_materials:
                    # select_for_update to lock rows
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

                # Step 2: Deduct raw materials
                total_material_cost = Decimal('0')
                for stock_id, (stock, needed) in stocks_to_update.items():
                    # Audit fields
                    qty_before = stock.quantity
                    qty_after = qty_before - needed
                    
                    OutletStock.objects.filter(id=stock_id).update(quantity=qty_after)
                    
                    # Create audit log
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
                    
                    # Create ProductionOrderItem
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

                # Step 3: Add finished product
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

                # Step 4: Finalize order
                order.status = ProductionOrder.Status.COMPLETED
                order.completed_at = timezone.now()
                order.quantity_produced = quantity_produced
                order.total_material_cost = total_material_cost
                order.notes = notes
                order.save()

            return Response(ProductionOrderSerializer(order).data)

        except Exception as e:
            # Re-raise for debugging if needed, or return structured error
            return Response(
                {"error": "An error occurred during production completion.", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class WorkInProgressViewSet(viewsets.ModelViewSet):
    queryset = WorkInProgress.objects.all()
    serializer_class = WorkInProgressSerializer
    filterset_fields = ['production_order']

    def perform_create(self, serializer):
        serializer.save(recorded_by_id=self.request.user.id)
