from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from products.models import Product
from .models import (
    OutletStock, PurchaseOrder, PurchaseOrderItem,
    StockTransfer, StockTransferItem, StockAuditLog,
)


def generate_po_number():
    """Generate PO number inside an atomic block to avoid race conditions."""
    today = timezone.now().strftime('%Y%m%d')
    prefix = f"PO-{today}-"
    last_po = (
        PurchaseOrder.objects
        .select_for_update()
        .filter(po_number__startswith=prefix)
        .order_by('-po_number')
        .first()
    )
    if last_po:
        last_num = int(last_po.po_number.split('-')[-1])
        next_num = last_num + 1
    else:
        next_num = 1
    return f"{prefix}{next_num:04d}"


def generate_transfer_number():
    """Generate transfer number inside an atomic block to avoid race conditions."""
    today = timezone.now().strftime('%Y%m%d')
    prefix = f"TRF-{today}-"
    last_transfer = (
        StockTransfer.objects
        .select_for_update()
        .filter(transfer_number__startswith=prefix)
        .order_by('-transfer_number')
        .first()
    )
    if last_transfer:
        last_num = int(last_transfer.transfer_number.split('-')[-1])
        next_num = last_num + 1
    else:
        next_num = 1
    return f"{prefix}{next_num:04d}"


def _create_audit_log(product, outlet, movement_type, quantity_change,
                      quantity_before, quantity_after, reference_type='',
                      reference_id=None, user_id=None, notes=''):
    StockAuditLog.objects.create(
        product=product,
        outlet=outlet,
        movement_type=movement_type,
        quantity_change=quantity_change,
        quantity_before=quantity_before,
        quantity_after=quantity_after,
        reference_type=reference_type,
        reference_id=reference_id,
        user_id=user_id,
        notes=notes,
    )


def receive_purchase_order(po, items_received, user_id):
    """
    Receive items for a purchase order atomically.

    Args:
        po: PurchaseOrder instance
        items_received: list of dicts with po_item_id, quantity_received
        user_id: ID of the user receiving

    Returns:
        Updated PurchaseOrder instance
    """
    if po.status in ('cancelled', 'received'):
        raise ValidationError(
            {'status': f'Cannot receive a {po.status} purchase order.'}
        )

    with transaction.atomic():
        all_fully_received = True

        for item_data in items_received:
            po_item = (
                PurchaseOrderItem.objects
                .select_for_update()
                .get(pk=item_data['po_item_id'], purchase_order=po)
            )
            qty = Decimal(str(item_data['quantity_received']))
            remaining = po_item.quantity_ordered - po_item.quantity_received
            if qty > remaining:
                raise ValidationError({
                    'items': f'Cannot receive {qty} of {po_item.product.name}. '
                             f'Remaining: {remaining}',
                })

            po_item.quantity_received += qty
            po_item.save(update_fields=['quantity_received'])

            # Update Product aggregate stock
            product = Product.objects.select_for_update().get(pk=po_item.product_id)
            qty_before = product.stock_quantity
            product.stock_quantity += qty
            product.save(update_fields=['stock_quantity', 'updated_at'])

            # Update OutletStock
            outlet_stock, _ = OutletStock.objects.select_for_update().get_or_create(
                outlet=po.outlet, product=product,
                defaults={'quantity': Decimal('0.000')},
            )
            os_qty_before = outlet_stock.quantity
            outlet_stock.quantity += qty
            outlet_stock.save(update_fields=['quantity', 'updated_at'])

            _create_audit_log(
                product=product, outlet=po.outlet,
                movement_type='purchase', quantity_change=qty,
                quantity_before=qty_before,
                quantity_after=product.stock_quantity,
                reference_type='PurchaseOrder', reference_id=po.pk,
                user_id=user_id,
            )

        # Check ALL items on the PO to determine status
        all_fully_received = all(
            item.quantity_received >= item.quantity_ordered
            for item in po.items.all()
        )
        po.status = 'received' if all_fully_received else 'partial'
        po.save(update_fields=['status', 'updated_at'])

    po.refresh_from_db()
    return po


def dispatch_transfer(transfer, user_id):
    """
    Dispatch a stock transfer: deduct from source outlet atomically.
    """
    if transfer.status != 'pending':
        raise ValidationError(
            {'status': f'Cannot dispatch a {transfer.status} transfer.'}
        )

    with transaction.atomic():
        for item in transfer.items.select_related('product').all():
            product = Product.objects.select_for_update().get(pk=item.product_id)

            # Check and deduct OutletStock at source
            outlet_stock, _ = OutletStock.objects.select_for_update().get_or_create(
                outlet=transfer.from_outlet, product=product,
                defaults={'quantity': Decimal('0.000')},
            )
            if outlet_stock.quantity < item.quantity:
                raise ValidationError({
                    'items': f'Insufficient stock for {product.name} at '
                             f'{transfer.from_outlet.name}. '
                             f'Available: {outlet_stock.quantity}, '
                             f'Requested: {item.quantity}',
                })

            os_qty_before = outlet_stock.quantity
            outlet_stock.quantity -= item.quantity
            outlet_stock.save(update_fields=['quantity', 'updated_at'])

            # Deduct from aggregate Product stock
            qty_before = product.stock_quantity
            product.stock_quantity -= item.quantity
            product.save(update_fields=['stock_quantity', 'updated_at'])

            _create_audit_log(
                product=product, outlet=transfer.from_outlet,
                movement_type='transfer_out',
                quantity_change=-item.quantity,
                quantity_before=qty_before,
                quantity_after=product.stock_quantity,
                reference_type='StockTransfer', reference_id=transfer.pk,
                user_id=user_id,
            )

        transfer.status = 'in_transit'
        transfer.save(update_fields=['status', 'updated_at'])

    transfer.refresh_from_db()
    return transfer


def receive_transfer(transfer, items_received, user_id):
    """
    Receive a stock transfer: add to destination outlet atomically.
    """
    if transfer.status != 'in_transit':
        raise ValidationError(
            {'status': f'Cannot receive a {transfer.status} transfer.'}
        )

    with transaction.atomic():
        for item_data in items_received:
            transfer_item = (
                StockTransferItem.objects
                .select_for_update()
                .get(pk=item_data['transfer_item_id'], transfer=transfer)
            )
            qty = Decimal(str(item_data['quantity_received']))
            remaining = transfer_item.quantity - transfer_item.quantity_received
            if qty > remaining:
                raise ValidationError({
                    'items': f'Cannot receive {qty} of {transfer_item.product.name}. '
                             f'Remaining: {remaining}',
                })

            transfer_item.quantity_received += qty
            transfer_item.save(update_fields=['quantity_received'])

            product = Product.objects.select_for_update().get(pk=transfer_item.product_id)

            # Add to destination OutletStock
            outlet_stock, _ = OutletStock.objects.select_for_update().get_or_create(
                outlet=transfer.to_outlet, product=product,
                defaults={'quantity': Decimal('0.000')},
            )
            outlet_stock.quantity += qty
            outlet_stock.save(update_fields=['quantity', 'updated_at'])

            # Add back to aggregate Product stock (was deducted on dispatch)
            qty_before = product.stock_quantity
            product.stock_quantity += qty
            product.save(update_fields=['stock_quantity', 'updated_at'])

            _create_audit_log(
                product=product, outlet=transfer.to_outlet,
                movement_type='transfer_in',
                quantity_change=qty,
                quantity_before=qty_before,
                quantity_after=product.stock_quantity,
                reference_type='StockTransfer', reference_id=transfer.pk,
                user_id=user_id,
            )

        transfer.status = 'completed'
        transfer.save(update_fields=['status', 'updated_at'])

    transfer.refresh_from_db()
    return transfer
