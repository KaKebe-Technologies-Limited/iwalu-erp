from datetime import datetime
from django.db import transaction
from django.db.models import F, Q, Sum, Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.permissions import IsAdminOrManager, IsCashierOrAbove
from .models import (
    Pump, Tank, TankReading, PumpReading,
    FuelDelivery, FuelReconciliation,
)
from .serializers import (
    PumpSerializer,
    TankSerializer, TankReadingSerializer, RecordTankReadingSerializer,
    PumpReadingSerializer, OpenPumpReadingSerializer, ClosePumpReadingSerializer,
    FuelDeliverySerializer, FuelDeliveryCreateSerializer,
    FuelReconciliationSerializer, ReconciliationRequestSerializer,
)
from . import services


class PumpViewSet(viewsets.ModelViewSet):
    queryset = Pump.objects.select_related('outlet', 'product').all()
    serializer_class = PumpSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'pump_number']
    filterset_fields = ['outlet', 'product', 'status']
    ordering_fields = ['pump_number', 'created_at']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy',
                           'activate', 'deactivate', 'set_maintenance'):
            return [IsAdminOrManager()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        pump = self.get_object()
        if pump.status not in ('inactive', 'maintenance'):
            return Response(
                {'error': f'Cannot activate a pump with status "{pump.status}".'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        pump.status = 'active'
        pump.save(update_fields=['status', 'updated_at'])
        return Response(PumpSerializer(pump).data)

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        pump = self.get_object()
        if pump.status != 'active':
            return Response(
                {'error': f'Cannot deactivate a pump with status "{pump.status}".'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        pump.status = 'inactive'
        pump.save(update_fields=['status', 'updated_at'])
        return Response(PumpSerializer(pump).data)

    @action(detail=True, methods=['post'], url_path='set-maintenance')
    def set_maintenance(self, request, pk=None):
        pump = self.get_object()
        if pump.status != 'active':
            return Response(
                {'error': f'Cannot set maintenance on a pump with status "{pump.status}".'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        pump.status = 'maintenance'
        pump.save(update_fields=['status', 'updated_at'])
        return Response(PumpSerializer(pump).data)


class TankViewSet(viewsets.ModelViewSet):
    queryset = Tank.objects.select_related('outlet', 'product').all()
    serializer_class = TankSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    filterset_fields = ['outlet', 'product', 'is_active']
    ordering_fields = ['name', 'current_level', 'created_at']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminOrManager()]
        if self.action == 'record_reading':
            return [IsCashierOrAbove()]
        return [IsAuthenticated()]

    @action(detail=True, methods=['post'], url_path='record-reading')
    def record_reading(self, request, pk=None):
        tank = self.get_object()
        serializer = RecordTankReadingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reading = services.record_tank_reading(
            tank=tank,
            reading_level=serializer.validated_data['reading_level'],
            reading_type=serializer.validated_data['reading_type'],
            user_id=request.user.pk,
            reading_at=serializer.validated_data.get('reading_at'),
            notes=serializer.validated_data.get('notes', ''),
        )
        return Response(
            TankReadingSerializer(reading).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get'])
    def readings(self, request, pk=None):
        tank = self.get_object()
        qs = TankReading.objects.filter(tank=tank)

        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if date_from:
            qs = qs.filter(reading_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(reading_at__date__lte=date_to)

        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(
                TankReadingSerializer(page, many=True).data,
            )
        return Response(TankReadingSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'], url_path='low-levels')
    def low_levels(self, request):
        qs = Tank.objects.select_related('outlet', 'product').filter(
            is_active=True,
        )
        outlet = request.query_params.get('outlet')
        if outlet:
            qs = qs.filter(outlet_id=outlet)

        qs = qs.filter(current_level__lte=F('reorder_level'))
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(TankSerializer(page, many=True).data)
        return Response(TankSerializer(qs, many=True).data)


class PumpReadingViewSet(viewsets.ModelViewSet):
    queryset = PumpReading.objects.select_related('pump', 'pump__outlet').all()
    serializer_class = PumpReadingSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['pump', 'shift', 'pump__outlet']
    ordering_fields = ['created_at']

    def get_permissions(self):
        if self.action in ('create', 'close_reading'):
            return [IsCashierOrAbove()]
        if self.action in ('update', 'partial_update', 'destroy'):
            return [IsAdminOrManager()]
        return [IsAuthenticated()]

    def destroy(self, request, *args, **kwargs):
        reading = self.get_object()
        if reading.closing_reading is not None:
            return Response(
                {'error': 'Cannot delete a closed pump reading. It is referenced by reconciliation data.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = OpenPumpReadingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            pump = Pump.objects.get(pk=data['pump_id'])
        except Pump.DoesNotExist:
            return Response(
                {'error': 'Pump not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if pump.status != 'active':
            return Response(
                {'error': f'Cannot create reading for pump with status "{pump.status}".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from sales.models import Shift
        try:
            shift = Shift.objects.get(pk=data['shift_id'])
        except Shift.DoesNotExist:
            return Response(
                {'error': 'Shift not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if shift.closed_at is not None:
            return Response(
                {'error': 'Cannot create pump reading for a closed shift.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if PumpReading.objects.filter(pump=pump, shift=shift).exists():
            return Response(
                {'error': 'A pump reading already exists for this pump and shift.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reading = PumpReading.objects.create(
            pump=pump,
            shift=shift,
            opening_reading=data['opening_reading'],
            recorded_by=request.user.pk,
        )
        return Response(
            PumpReadingSerializer(reading).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        reading = self.get_object()
        serializer = ClosePumpReadingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = services.close_pump_reading(
            pump_reading=reading,
            closing_reading=serializer.validated_data['closing_reading'],
            notes=serializer.validated_data.get('notes', ''),
        )
        return Response(PumpReadingSerializer(updated).data)


class FuelDeliveryViewSet(viewsets.ModelViewSet):
    queryset = FuelDelivery.objects.select_related('tank', 'supplier', 'tank__outlet').all()
    serializer_class = FuelDeliverySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['delivery_note_number']
    filterset_fields = ['tank', 'supplier', 'tank__outlet']
    ordering_fields = ['delivery_date', 'created_at']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminOrManager()]
        return [IsAuthenticated()]

    def destroy(self, request, *args, **kwargs):
        return Response(
            {'error': 'Fuel deliveries cannot be deleted as they affect tank levels and inventory. '
                      'Contact admin for corrections.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def create(self, request, *args, **kwargs):
        serializer = FuelDeliveryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            tank = Tank.objects.get(pk=data['tank_id'])
        except Tank.DoesNotExist:
            return Response(
                {'error': 'Tank not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        from inventory.models import Supplier
        try:
            supplier = Supplier.objects.get(pk=data['supplier_id'])
        except Supplier.DoesNotExist:
            return Response(
                {'error': 'Supplier not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        delivery = services.process_fuel_delivery(
            tank=tank,
            supplier=supplier,
            volume_received=data['volume_received'],
            unit_cost=data['unit_cost'],
            delivery_date=data['delivery_date'],
            received_by=request.user.pk,
            delivery_note_number=data.get('delivery_note_number', ''),
            volume_ordered=data.get('volume_ordered'),
            notes=data.get('notes', ''),
        )
        return Response(
            FuelDeliverySerializer(delivery).data,
            status=status.HTTP_201_CREATED,
        )


class FuelReconciliationViewSet(viewsets.ModelViewSet):
    queryset = FuelReconciliation.objects.select_related('tank', 'outlet').all()
    serializer_class = FuelReconciliationSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['outlet', 'tank', 'variance_type', 'status']
    ordering_fields = ['date', 'variance', 'created_at']

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy',
                           'calculate', 'confirm'):
            return [IsAdminOrManager()]
        return [IsAuthenticated()]

    def destroy(self, request, *args, **kwargs):
        recon = self.get_object()
        if recon.status == 'confirmed':
            return Response(
                {'error': 'Confirmed reconciliations cannot be deleted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['post'])
    def calculate(self, request):
        serializer = ReconciliationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            tank = Tank.objects.get(pk=data['tank_id'])
        except Tank.DoesNotExist:
            return Response(
                {'error': 'Tank not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        recon = services.calculate_reconciliation(
            tank=tank,
            date=data['date'],
            user_id=request.user.pk,
            closing_stock=data.get('closing_stock'),
            notes=data.get('notes', ''),
        )
        return Response(
            FuelReconciliationSerializer(recon).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        with transaction.atomic():
            recon = FuelReconciliation.objects.select_for_update().get(pk=pk)
            if recon.status != 'draft':
                return Response(
                    {'error': 'Only draft reconciliations can be confirmed.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            recon.status = 'confirmed'
            recon.save(update_fields=['status', 'updated_at'])

            # Update tank level to match confirmed closing stock
            tank = Tank.objects.select_for_update().get(pk=recon.tank_id)
            tank.current_level = recon.closing_stock
            tank.save(update_fields=['current_level', 'updated_at'])

        return Response(FuelReconciliationSerializer(recon).data)

    @action(detail=False, methods=['get'], url_path='variance-alerts')
    def variance_alerts(self, request):
        outlet = request.query_params.get('outlet')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        qs = services.get_variance_alerts(
            outlet_id=outlet,
            date_from=date_from,
            date_to=date_to,
        )
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(
                FuelReconciliationSerializer(page, many=True).data,
            )
        return Response(FuelReconciliationSerializer(qs, many=True).data)


# ---------- Report Views ----------

@api_view(['GET'])
@permission_classes([IsAdminOrManager])
def daily_pump_report(request):
    """Per-pump dispensing data for a given date and outlet."""
    date_str = request.query_params.get('date')
    outlet_id = request.query_params.get('outlet')

    if not date_str:
        return Response(
            {'error': 'date parameter is required (YYYY-MM-DD).'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        report_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return Response(
            {'error': 'Invalid date format. Use YYYY-MM-DD.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    readings = PumpReading.objects.select_related(
        'pump', 'pump__product', 'pump__outlet',
    ).filter(created_at__date=report_date)

    if outlet_id:
        readings = readings.filter(pump__outlet_id=outlet_id)

    pump_data = []
    for r in readings:
        pump_data.append({
            'pump_number': r.pump.pump_number,
            'pump_name': r.pump.name,
            'product': r.pump.product.name,
            'outlet': r.pump.outlet.name,
            'shift_id': r.shift_id,
            'opening_reading': r.opening_reading,
            'closing_reading': r.closing_reading,
            'volume_dispensed': r.volume_dispensed,
            'recorded_by': r.recorded_by,
        })

    totals = (
        readings
        .filter(closing_reading__isnull=False)
        .values('pump__product__name')
        .annotate(total_volume=Sum(F('closing_reading') - F('opening_reading')))
    )

    return Response({
        'date': report_date,
        'pumps': pump_data,
        'totals_by_product': list(totals),
    })


@api_view(['GET'])
@permission_classes([IsAdminOrManager])
def variance_report(request):
    """Aggregated variance data over a date range."""
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    outlet_id = request.query_params.get('outlet')

    if not date_from or not date_to:
        return Response(
            {'error': 'date_from and date_to are required (YYYY-MM-DD).'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
    except ValueError:
        return Response(
            {'error': 'Invalid date format. Use YYYY-MM-DD.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    qs = FuelReconciliation.objects.select_related(
        'tank', 'tank__product', 'outlet',
    ).filter(date__gte=date_from, date__lte=date_to)

    if outlet_id:
        qs = qs.filter(outlet_id=outlet_id)

    reconciliations = FuelReconciliationSerializer(qs, many=True).data

    summary = qs.aggregate(
        total_variance=Sum('variance'),
        loss_count=Count('id', filter=Q(variance_type='loss')),
        gain_count=Count('id', filter=Q(variance_type='gain')),
        within_tolerance_count=Count('id', filter=Q(variance_type='within_tolerance')),
    )

    return Response({
        'date_from': date_from,
        'date_to': date_to,
        'reconciliations': reconciliations,
        'summary': summary,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tank_levels_summary(request):
    """Current tank levels across all tanks or filtered by outlet."""
    outlet_id = request.query_params.get('outlet')

    qs = Tank.objects.select_related('outlet', 'product').filter(is_active=True)
    if outlet_id:
        qs = qs.filter(outlet_id=outlet_id)

    return Response(TankSerializer(qs, many=True).data)
