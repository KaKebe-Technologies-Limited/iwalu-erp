from django.db import models
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.permissions import IsAdminOrManager
from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer, StockAdjustmentSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    search_fields = ['name']
    filterset_fields = ['business_unit', 'parent', 'is_active']
    ordering_fields = ['name', 'created_at']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminOrManager()]
        return [IsAuthenticated()]


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related('category').all()
    serializer_class = ProductSerializer
    search_fields = ['name', 'sku', 'barcode']
    filterset_fields = ['category', 'is_active', 'track_stock']
    ordering_fields = ['name', 'selling_price', 'stock_quantity', 'created_at']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy',
                           'adjust_stock'):
            return [IsAdminOrManager()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        products = Product.objects.filter(
            track_stock=True,
            is_active=True,
            stock_quantity__lte=models.F('reorder_level'),
        ).select_related('category')
        page = self.paginate_queryset(products)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def adjust_stock(self, request, pk=None):
        from django.db import transaction
        from inventory.models import OutletStock, StockAuditLog

        serializer = StockAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        qty_change = serializer.validated_data['quantity']
        reason = serializer.validated_data['reason']
        outlet_id = request.data.get('outlet_id')

        # Validate outlet up front if provided
        outlet = None
        if outlet_id:
            from outlets.models import Outlet
            try:
                outlet = Outlet.objects.get(pk=outlet_id)
            except Outlet.DoesNotExist:
                return Response(
                    {'outlet_id': 'Outlet not found.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        with transaction.atomic():
            product = Product.objects.select_for_update().get(pk=pk)
            qty_before = product.stock_quantity
            product.stock_quantity += qty_change
            product.save(update_fields=['stock_quantity', 'updated_at'])

            if outlet:
                outlet_stock, _ = OutletStock.objects.select_for_update().get_or_create(
                    outlet=outlet, product=product,
                    defaults={'quantity': 0},
                )
                outlet_stock.quantity += qty_change
                outlet_stock.save(update_fields=['quantity', 'updated_at'])

            StockAuditLog.objects.create(
                product=product,
                outlet=outlet,
                movement_type='adjustment',
                quantity_change=qty_change,
                quantity_before=qty_before,
                quantity_after=product.stock_quantity,
                reference_type='StockAdjustment',
                user_id=request.user.id,
                notes=reason,
            )

        product.refresh_from_db()
        return Response(ProductSerializer(product).data)
