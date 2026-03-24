from datetime import date, timedelta
from decimal import Decimal
from django.db.models import Sum, Count, Avg, F, Q
from django.db.models.functions import TruncHour, TruncDate
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.permissions import IsAdminOrManager
from sales.models import Sale, SaleItem, Payment, Shift
from products.models import Product
from inventory.models import OutletStock, StockAuditLog


def _parse_dates(request):
    today = timezone.now().date()
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    try:
        date_from = date.fromisoformat(date_from) if date_from else today
    except ValueError:
        date_from = today
    try:
        date_to = date.fromisoformat(date_to) if date_to else today
    except ValueError:
        date_to = today
    return date_from, date_to


def _filter_sales(date_from, date_to, outlet=None):
    qs = Sale.objects.filter(
        status='completed',
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
    )
    if outlet:
        qs = qs.filter(outlet_id=outlet)
    return qs


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sales_summary(request):
    date_from, date_to = _parse_dates(request)
    outlet = request.query_params.get('outlet')
    sales = _filter_sales(date_from, date_to, outlet)

    totals = sales.aggregate(
        total_sales=Count('id'),
        total_revenue=Sum('grand_total'),
        total_tax=Sum('tax_total'),
        total_discount=Sum('discount_total'),
        avg_sale=Avg('grand_total'),
    )
    # Handle None values
    for key in totals:
        if totals[key] is None:
            totals[key] = Decimal('0.00') if key != 'total_sales' else 0

    totals['date_from'] = date_from.isoformat()
    totals['date_to'] = date_to.isoformat()
    return Response(totals)


@api_view(['GET'])
@permission_classes([IsAdminOrManager])
def sales_by_outlet(request):
    date_from, date_to = _parse_dates(request)
    sales = _filter_sales(date_from, date_to)

    data = (
        sales
        .values('outlet', outlet_name=F('outlet__name'))
        .annotate(
            total_sales=Count('id'),
            total_revenue=Sum('grand_total'),
        )
        .order_by('-total_revenue')
    )
    return Response(list(data))


@api_view(['GET'])
@permission_classes([IsAdminOrManager])
def sales_by_product(request):
    date_from, date_to = _parse_dates(request)
    outlet = request.query_params.get('outlet')
    category = request.query_params.get('category')

    items = SaleItem.objects.filter(
        sale__status='completed',
        sale__created_at__date__gte=date_from,
        sale__created_at__date__lte=date_to,
    )
    if outlet:
        items = items.filter(sale__outlet_id=outlet)
    if category:
        items = items.filter(product__category_id=category)

    data = (
        items
        .values('product', product_name=F('product__name'),
                product_sku=F('product__sku'))
        .annotate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum('line_total'),
        )
        .order_by('-total_revenue')[:20]
    )
    return Response(list(data))


@api_view(['GET'])
@permission_classes([IsAdminOrManager])
def sales_by_payment_method(request):
    date_from, date_to = _parse_dates(request)
    outlet = request.query_params.get('outlet')

    payments = Payment.objects.filter(
        sale__status='completed',
        sale__created_at__date__gte=date_from,
        sale__created_at__date__lte=date_to,
    )
    if outlet:
        payments = payments.filter(sale__outlet_id=outlet)

    data = (
        payments
        .values('payment_method')
        .annotate(
            count=Count('id'),
            total_amount=Sum('amount'),
        )
        .order_by('-total_amount')
    )
    return Response(list(data))


@api_view(['GET'])
@permission_classes([IsAdminOrManager])
def hourly_sales(request):
    date_from, date_to = _parse_dates(request)
    outlet = request.query_params.get('outlet')
    sales = _filter_sales(date_from, date_to, outlet)

    data = (
        sales
        .annotate(hour=TruncHour('created_at'))
        .values('hour')
        .annotate(
            total_sales=Count('id'),
            total_revenue=Sum('grand_total'),
        )
        .order_by('hour')
    )
    return Response(list(data))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stock_levels(request):
    outlet = request.query_params.get('outlet')
    category = request.query_params.get('category')

    if outlet:
        qs = (
            OutletStock.objects
            .select_related('product', 'outlet')
            .filter(product__is_active=True)
        )
        if outlet:
            qs = qs.filter(outlet_id=outlet)
        if category:
            qs = qs.filter(product__category_id=category)

        data = list(qs.values(
            'outlet', 'product', 'quantity',
            outlet_name=F('outlet__name'),
            product_name=F('product__name'),
            product_sku=F('product__sku'),
            reorder_level=F('product__reorder_level'),
        ).order_by('product__name'))
    else:
        qs = Product.objects.filter(is_active=True, track_stock=True)
        if category:
            qs = qs.filter(category_id=category)
        data = list(qs.values(
            'id', 'name', 'sku', 'stock_quantity', 'reorder_level',
            category_name=F('category__name'),
        ).order_by('name'))

    return Response(data)


@api_view(['GET'])
@permission_classes([IsAdminOrManager])
def stock_movement(request):
    date_from, date_to = _parse_dates(request)
    product = request.query_params.get('product')
    outlet = request.query_params.get('outlet')

    qs = StockAuditLog.objects.filter(
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
    )
    if product:
        qs = qs.filter(product_id=product)
    if outlet:
        qs = qs.filter(outlet_id=outlet)

    data = (
        qs
        .values('movement_type')
        .annotate(
            count=Count('id'),
            total_quantity=Sum('quantity_change'),
        )
        .order_by('movement_type')
    )
    return Response(list(data))


@api_view(['GET'])
@permission_classes([IsAdminOrManager])
def shift_summary(request):
    date_from, date_to = _parse_dates(request)
    outlet = request.query_params.get('outlet')
    user_id = request.query_params.get('user_id')

    shifts = Shift.objects.filter(
        status='closed',
        opened_at__date__gte=date_from,
        opened_at__date__lte=date_to,
    )
    if outlet:
        shifts = shifts.filter(outlet_id=outlet)
    if user_id:
        shifts = shifts.filter(user_id=user_id)

    data = list(shifts.values(
        'id', 'outlet', 'user_id', 'opening_cash', 'closing_cash',
        'expected_cash', 'opened_at', 'closed_at',
        outlet_name=F('outlet__name'),
    ).annotate(
        total_sales=Count('sales', filter=Q(sales__status='completed')),
        total_revenue=Sum('sales__grand_total', filter=Q(sales__status='completed')),
    ).order_by('-opened_at'))

    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard(request):
    today = timezone.now().date()
    outlet = request.query_params.get('outlet')
    user = request.user

    # Role-scoped: cashier/attendant see only their current shift outlet
    if user.role in ('cashier', 'attendant'):
        current_shift = Shift.objects.filter(
            user_id=user.id, status='open',
        ).first()
        if current_shift:
            outlet = str(current_shift.outlet_id)
        else:
            return Response({
                'today_sales': 0,
                'today_revenue': Decimal('0.00'),
                'active_shifts': 0,
                'low_stock_count': 0,
            })

    sales = _filter_sales(today, today, outlet)
    totals = sales.aggregate(
        today_sales=Count('id'),
        today_revenue=Sum('grand_total'),
    )

    active_shifts = Shift.objects.filter(status='open')
    if outlet:
        active_shifts = active_shifts.filter(outlet_id=outlet)

    low_stock_count = Product.objects.filter(
        track_stock=True, is_active=True,
        stock_quantity__lte=F('reorder_level'),
    ).count()

    return Response({
        'today_sales': totals['today_sales'] or 0,
        'today_revenue': totals['today_revenue'] or Decimal('0.00'),
        'active_shifts': active_shifts.count(),
        'low_stock_count': low_stock_count,
        'date': today.isoformat(),
    })
