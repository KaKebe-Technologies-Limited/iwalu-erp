import logging
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from products.models import Product
from inventory.models import OutletStock, StockAuditLog
from .models import (
    Tank, TankReading, PumpReading, FuelDelivery, FuelReconciliation,
)

logger = logging.getLogger(__name__)

VARIANCE_TOLERANCE_PERCENT = Decimal('0.50')


def record_tank_reading(tank, reading_level, reading_type, user_id,
                        reading_at=None, notes=''):
    """Record a tank level reading and update the tank's current level."""
    reading_level = Decimal(str(reading_level))

    if reading_level < 0:
        raise ValidationError({'reading_level': 'Reading level cannot be negative.'})
    if reading_level > tank.capacity:
        raise ValidationError({
            'reading_level': f'Reading level ({reading_level}L) exceeds '
                             f'tank capacity ({tank.capacity}L).',
        })

    with transaction.atomic():
        tank = Tank.objects.select_for_update().get(pk=tank.pk)
        reading = TankReading.objects.create(
            tank=tank,
            reading_level=reading_level,
            reading_type=reading_type,
            recorded_by=user_id,
            reading_at=reading_at or timezone.now(),
            notes=notes,
        )
        tank.current_level = reading_level
        tank.save(update_fields=['current_level', 'updated_at'])

    return reading


def process_fuel_delivery(tank, supplier, volume_received, unit_cost,
                          delivery_date, received_by, delivery_note_number='',
                          volume_ordered=None, notes=''):
    """Process a fuel delivery: update tank level, inventory, and audit log."""
    volume_received = Decimal(str(volume_received))
    unit_cost = Decimal(str(unit_cost))

    if volume_received <= 0:
        raise ValidationError({'volume_received': 'Volume must be positive.'})
    if unit_cost <= 0:
        raise ValidationError({'unit_cost': 'Unit cost must be positive.'})

    with transaction.atomic():
        tank = Tank.objects.select_for_update().get(pk=tank.pk)

        if tank.current_level + volume_received > tank.capacity:
            raise ValidationError({
                'volume_received': f'Delivery of {volume_received}L would exceed '
                                   f'tank capacity. Current: {tank.current_level}L, '
                                   f'Capacity: {tank.capacity}L.',
            })

        tank_level_before = tank.current_level
        tank_level_after = tank_level_before + volume_received
        total_cost = volume_received * unit_cost

        delivery = FuelDelivery.objects.create(
            tank=tank,
            supplier=supplier,
            delivery_date=delivery_date,
            volume_ordered=Decimal(str(volume_ordered)) if volume_ordered else None,
            volume_received=volume_received,
            unit_cost=unit_cost,
            total_cost=total_cost,
            delivery_note_number=delivery_note_number,
            tank_level_before=tank_level_before,
            tank_level_after=tank_level_after,
            received_by=received_by,
            notes=notes,
        )

        # Update tank level
        tank.current_level = tank_level_after
        tank.save(update_fields=['current_level', 'updated_at'])

        # Create post-delivery tank reading
        TankReading.objects.create(
            tank=tank,
            reading_level=tank_level_after,
            reading_type='delivery',
            recorded_by=received_by,
            reading_at=delivery_date,
            notes=f'Post-delivery reading. Delivery #{delivery.pk}',
        )

        # Sync with inventory module
        product = Product.objects.select_for_update().get(pk=tank.product_id)
        qty_before = product.stock_quantity
        product.stock_quantity += volume_received
        product.save(update_fields=['stock_quantity', 'updated_at'])

        outlet_stock, _ = OutletStock.objects.select_for_update().get_or_create(
            outlet=tank.outlet, product=product,
            defaults={'quantity': Decimal('0.000')},
        )
        outlet_stock.quantity += volume_received
        outlet_stock.save(update_fields=['quantity', 'updated_at'])

        StockAuditLog.objects.create(
            product=product,
            outlet=tank.outlet,
            movement_type='purchase',
            quantity_change=volume_received,
            quantity_before=qty_before,
            quantity_after=product.stock_quantity,
            reference_type='FuelDelivery',
            reference_id=delivery.pk,
            user_id=received_by,
            notes=f'Fuel delivery to {tank.name}',
        )

        # Create journal entry if finance module is available
        try:
            from finance.services import create_purchase_journal_entry
        except ImportError:
            logger.info('Finance module not installed, skipping journal entry.')
        else:
            try:
                create_purchase_journal_entry(delivery, total_cost, received_by)
            except Exception:
                logger.error(
                    'Failed to create journal entry for fuel delivery %s. '
                    'Manual journal entry may be required.',
                    delivery.pk, exc_info=True,
                )

    return delivery


def close_pump_reading(pump_reading, closing_reading, notes=''):
    """Close a pump reading with the closing meter value."""
    closing_reading = Decimal(str(closing_reading))

    with transaction.atomic():
        pump_reading = PumpReading.objects.select_for_update().get(pk=pump_reading.pk)

        if pump_reading.closing_reading is not None:
            raise ValidationError({'closing_reading': 'This pump reading is already closed.'})
        if closing_reading < pump_reading.opening_reading:
            raise ValidationError({
                'closing_reading': f'Closing reading ({closing_reading}) cannot be less '
                                   f'than opening reading ({pump_reading.opening_reading}).',
            })

        pump_reading.closing_reading = closing_reading
        if notes:
            pump_reading.notes = notes
        pump_reading.save(update_fields=['closing_reading', 'notes', 'updated_at'])

    return pump_reading


def calculate_reconciliation(tank, date, user_id, closing_stock=None, notes=''):
    """
    Calculate daily fuel reconciliation for a tank.

    Compares expected closing stock (opening + received - dispensed)
    against actual closing stock to detect variance.
    """
    with transaction.atomic():
        tank = Tank.objects.select_for_update().get(pk=tank.pk)

        # 1. Opening stock: previous day's reconciliation closing, or earliest
        #    reading of the day, or current tank level
        prev_recon = (
            FuelReconciliation.objects
            .filter(tank=tank, date__lt=date)
            .order_by('-date')
            .first()
        )
        if prev_recon:
            opening_stock = prev_recon.closing_stock
        else:
            earliest_reading = (
                TankReading.objects
                .filter(tank=tank, reading_at__date=date)
                .order_by('reading_at')
                .first()
            )
            opening_stock = earliest_reading.reading_level if earliest_reading else tank.current_level

        # 2. Closing stock: provided value, latest reading of the day, or current level
        if closing_stock is not None:
            closing_stock = Decimal(str(closing_stock))
        else:
            latest_reading = (
                TankReading.objects
                .filter(tank=tank, reading_at__date=date)
                .order_by('-reading_at')
                .first()
            )
            closing_stock = latest_reading.reading_level if latest_reading else tank.current_level

        # 3. Total received: fuel deliveries to this tank on the given date
        total_received = (
            FuelDelivery.objects
            .filter(tank=tank, delivery_date__date=date)
            .aggregate(total=Sum('volume_received'))
        )['total'] or Decimal('0.000')

        # 4. Total dispensed: sum of completed pump readings for pumps using
        #    this tank's product at this outlet, created on the given date
        from django.db.models import F

        total_dispensed = (
            PumpReading.objects
            .filter(
                pump__outlet=tank.outlet,
                pump__product=tank.product,
                closing_reading__isnull=False,
                created_at__date=date,
            )
            .aggregate(
                total=Sum(F('closing_reading') - F('opening_reading'))
            )
        )['total'] or Decimal('0.000')

        # 5. Calculate expected and variance
        expected_closing = opening_stock + total_received - total_dispensed
        variance = closing_stock - expected_closing

        if expected_closing > 0:
            variance_percentage = (variance / expected_closing) * 100
        else:
            variance_percentage = Decimal('0.00')

        if abs(variance_percentage) <= VARIANCE_TOLERANCE_PERCENT:
            variance_type = 'within_tolerance'
        elif variance > 0:
            variance_type = 'gain'
        else:
            variance_type = 'loss'

        # 6. Guard against overwriting confirmed reconciliations
        existing = FuelReconciliation.objects.filter(
            date=date, tank=tank, status='confirmed',
        ).first()
        if existing:
            raise ValidationError({
                'date': 'A confirmed reconciliation already exists for this date and tank.',
            })

        # 7. Create or update reconciliation
        recon, _ = FuelReconciliation.objects.update_or_create(
            date=date,
            tank=tank,
            defaults={
                'outlet': tank.outlet,
                'opening_stock': opening_stock,
                'closing_stock': closing_stock,
                'total_received': total_received,
                'total_dispensed': total_dispensed,
                'expected_closing': expected_closing,
                'variance': variance,
                'variance_percentage': round(variance_percentage, 2),
                'variance_type': variance_type,
                'reconciled_by': user_id,
                'notes': notes,
            },
        )

    return recon


def get_variance_alerts(outlet_id=None, date_from=None, date_to=None):
    """Query reconciliations with non-tolerable variance."""
    qs = FuelReconciliation.objects.filter(
        variance_type__in=['gain', 'loss'],
    ).select_related('tank', 'outlet')

    if outlet_id:
        qs = qs.filter(outlet_id=outlet_id)
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)

    return qs
