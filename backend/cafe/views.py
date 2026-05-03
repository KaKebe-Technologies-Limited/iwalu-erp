from django.shortcuts import get_object_or_404
from django.db import transaction, IntegrityError
from django.utils import timezone
from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from decimal import Decimal

from .models import MenuCategory, MenuItem, MenuItemIngredient, MenuOrder, MenuOrderItem, WasteLog
from .serializers import (
    MenuCategorySerializer, MenuItemSerializer, MenuItemIngredientSerializer,
    MenuOrderSerializer, MenuOrderItemSerializer, WasteLogSerializer
)
from users.permissions import IsAdminOrManager, IsCashierOrAbove, IsAccountant, IsAccountantOrAbove
from inventory.models import OutletStock, StockAuditLog
from products.models import Product


ALLOWED_ORDER_TRANSITIONS = {
    'pending': ['preparing', 'cancelled'],
    'preparing': ['ready', 'cancelled'],
    'ready': ['completed', 'cancelled'],
    'completed': [],
    'cancelled': [],
}


class MenuCategoryViewSet(viewsets.ModelViewSet):
    queryset = MenuCategory.objects.all()
    serializer_class = MenuCategorySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering_fields = ['display_order', 'name']

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == 'list':
            return queryset.filter(is_active=True)
        return queryset

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminOrManager()]
        return [permissions.IsAuthenticated()]


class MenuItemViewSet(viewsets.ModelViewSet):
    queryset = MenuItem.objects.select_related('category').prefetch_related(
        'ingredients', 'ingredients__product'
    ).all()
    serializer_class = MenuItemSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'is_available', 'has_bom']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'price', 'category__name']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'update_bom']:
            return [IsAdminOrManager()]
        if self.action == 'cost':
            return [(IsAdminOrManager | IsAccountant)()]
        return [permissions.IsAuthenticated()]

    @action(detail=True, methods=['post'], url_path='update-bom')
    def update_bom(self, request, pk=None):
        menu_item = self.get_object()
        ingredients_data = request.data.get('ingredients', [])

        if not isinstance(ingredients_data, list):
            return Response({"error": "Ingredients must be a list"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            MenuItemIngredient.objects.filter(menu_item=menu_item).delete()

            for item in ingredients_data:
                product = get_object_or_404(Product, id=item.get('product_id'))
                qty = item.get('quantity_per_serving')
                unit = item.get('unit')
                if not qty or not unit:
                    return Response(
                        {"error": "Each ingredient requires product_id, quantity_per_serving, and unit"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                MenuItemIngredient.objects.create(
                    menu_item=menu_item,
                    product=product,
                    quantity_per_serving=qty,
                    unit=unit
                )

            menu_item.has_bom = True
            menu_item.save(update_fields=['has_bom', 'updated_at'])
            menu_item.recompute_cost_price()

        return Response({
            "status": "success",
            "cost_price": str(menu_item.cost_price),
            "ingredients_count": menu_item.ingredients.count()
        })

    @action(detail=True, methods=['get'])
    def cost(self, request, pk=None):
        menu_item = self.get_object()
        ingredients = menu_item.ingredients.select_related('product').all()

        ingredient_list = []
        for ing in ingredients:
            line_cost = (ing.product.cost_price or Decimal('0')) * ing.quantity_per_serving
            ingredient_list.append({
                "product": ing.product.name,
                "quantity": f"{ing.quantity_per_serving} {ing.unit}",
                "unit_cost": str(ing.product.cost_price or 0),
                "line_cost": str(line_cost)
            })

        gross_margin = Decimal('0')
        if menu_item.price > 0:
            gross_margin = ((menu_item.price - menu_item.cost_price) / menu_item.price) * 100

        return Response({
            "menu_item": menu_item.name,
            "selling_price": str(menu_item.price),
            "cost_price": str(menu_item.cost_price),
            "gross_margin_pct": f"{gross_margin:.2f}",
            "ingredients": ingredient_list
        })


class MenuOrderViewSet(viewsets.ModelViewSet):
    queryset = MenuOrder.objects.select_related('outlet').prefetch_related(
        'items', 'items__menu_item'
    ).all()
    serializer_class = MenuOrderSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'order_type']
    search_fields = ['order_number', 'table_number']
    ordering_fields = ['created_at', 'total_amount']

    def get_permissions(self):
        return [IsCashierOrAbove()]

    def _generate_order_number(self):
        date_str = timezone.now().strftime('%Y%m%d')
        count = MenuOrder.objects.filter(
            order_number__startswith=f"ORD-{date_str}"
        ).count() + 1
        return f"ORD-{date_str}-{count:04d}"

    def create(self, request, *args, **kwargs):
        items_data = request.data.get('items', [])
        outlet_id = request.data.get('outlet_id')

        if not items_data:
            return Response({"error": "No items in order"}, status=status.HTTP_400_BAD_REQUEST)
        if not outlet_id:
            return Response({"error": "outlet_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        from outlets.models import Outlet
        outlet = get_object_or_404(Outlet, id=outlet_id)

        with transaction.atomic():
            stock_requirements = {}
            validated_items = []

            for item_data in items_data:
                menu_item = get_object_or_404(MenuItem, id=item_data.get('menu_item_id'))
                if not menu_item.is_available:
                    return Response(
                        {"error": f"Item '{menu_item.name}' is currently unavailable"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                quantity = int(item_data.get('quantity', 1))
                validated_items.append((menu_item, quantity, item_data.get('special_instructions', '')))

                if menu_item.has_bom:
                    for ing in menu_item.ingredients.select_related('product').all():
                        prod_id = ing.product_id
                        required_qty = ing.quantity_per_serving * quantity
                        stock_requirements[prod_id] = stock_requirements.get(prod_id, Decimal('0')) + required_qty

            shortages = []
            for prod_id, required_qty in stock_requirements.items():
                try:
                    stock = OutletStock.objects.get(outlet_id=outlet_id, product_id=prod_id)
                    if stock.quantity < required_qty:
                        shortages.append({
                            "product": stock.product.name,
                            "required": f"{required_qty}",
                            "available": f"{stock.quantity}"
                        })
                except OutletStock.DoesNotExist:
                    product = Product.objects.get(id=prod_id)
                    shortages.append({
                        "product": product.name,
                        "required": f"{required_qty}",
                        "available": "0.000"
                    })

            if shortages:
                return Response({"error": "Insufficient stock", "shortages": shortages}, status=status.HTTP_400_BAD_REQUEST)

            for attempt in range(10):
                try:
                    order = MenuOrder.objects.create(
                        order_number=self._generate_order_number(),
                        order_type=request.data.get('order_type'),
                        table_number=request.data.get('table_number', ''),
                        outlet=outlet,
                        cashier_id=request.user.id,
                        notes=request.data.get('notes', '')
                    )
                    break
                except IntegrityError:
                    if attempt == 9:
                        raise
                    continue

            total_amount = Decimal('0')
            for menu_item, quantity, instructions in validated_items:
                order_item = MenuOrderItem.objects.create(
                    order=order,
                    menu_item=menu_item,
                    quantity=quantity,
                    unit_price=menu_item.price,
                    special_instructions=instructions
                )
                total_amount += order_item.line_total

                if menu_item.has_bom:
                    for ing in menu_item.ingredients.select_related('product').all():
                        stock = OutletStock.objects.get(outlet_id=outlet_id, product_id=ing.product_id)
                        qty_before = stock.quantity
                        stock.quantity -= (ing.quantity_per_serving * quantity)
                        stock.save()

                        StockAuditLog.objects.create(
                            product=ing.product,
                            outlet_id=outlet_id,
                            movement_type='sale',
                            quantity_change=-(ing.quantity_per_serving * quantity),
                            quantity_before=qty_before,
                            quantity_after=stock.quantity,
                            reference_type='menu_order',
                            reference_id=order.id,
                            user_id=request.user.id,
                            notes=f"Cafe Order {order.order_number}"
                        )

            order.total_amount = total_amount
            order.save()

        serializer = self.get_serializer(order)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='status')
    def update_status(self, request, pk=None):
        order = self.get_object()
        new_status = request.data.get('status')

        valid_statuses = [s[0] for s in MenuOrder.Status.choices]
        if new_status not in valid_statuses:
            return Response({"error": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST)

        allowed = ALLOWED_ORDER_TRANSITIONS.get(order.status, [])
        if new_status not in allowed:
            return Response(
                {"error": f"Cannot transition from '{order.status}' to '{new_status}'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            if new_status == MenuOrder.Status.CANCELLED:
                for item in order.items.select_related('menu_item').all():
                    if item.menu_item.has_bom:
                        for ing in item.menu_item.ingredients.select_related('product').all():
                            try:
                                stock = OutletStock.objects.get(
                                    outlet_id=order.outlet_id, product_id=ing.product_id
                                )
                            except OutletStock.DoesNotExist:
                                continue
                            qty_before = stock.quantity
                            qty_to_restore = ing.quantity_per_serving * item.quantity
                            stock.quantity += qty_to_restore
                            stock.save()

                            StockAuditLog.objects.create(
                                product=ing.product,
                                outlet_id=order.outlet_id,
                                movement_type='void',
                                quantity_change=qty_to_restore,
                                quantity_before=qty_before,
                                quantity_after=stock.quantity,
                                reference_type='menu_order_cancel',
                                reference_id=order.id,
                                user_id=request.user.id,
                                notes=f"Cancelled Order {order.order_number}"
                            )

            order.status = new_status
            order.save()

        return Response({
            "id": order.id,
            "status": order.status,
            "message": f"Order is now {order.get_status_display()}."
        })


class WasteLogViewSet(viewsets.ModelViewSet):
    queryset = WasteLog.objects.select_related('product').all()
    serializer_class = WasteLogSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['reason', 'product']
    ordering_fields = ['recorded_at', 'quantity']
    http_method_names = ['get', 'post', 'head', 'options']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAdminOrManager() | IsAccountant()]
        return [IsCashierOrAbove()]

    def perform_create(self, serializer):
        serializer.save(recorded_by_id=self.request.user.id)
