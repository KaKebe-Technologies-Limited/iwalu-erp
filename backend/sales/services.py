import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

logger = logging.getLogger(__name__)

from products.models import Product
from .models import Discount, Sale, SaleItem, Payment

# Lazy imports to avoid circular imports
def _get_inventory_models():
    from inventory.models import OutletStock, StockAuditLog
    return OutletStock, StockAuditLog


def generate_receipt_number(outlet_id):
    """Generate receipt number: OUT{id}-YYYYMMDD-NNNN"""
    today = timezone.now().strftime('%Y%m%d')
    prefix = f"OUT{outlet_id}-{today}-"
    last_sale = (
        Sale.objects
        .filter(receipt_number__startswith=prefix)
        .order_by('-receipt_number')
        .first()
    )
    if last_sale:
        last_num = int(last_sale.receipt_number.split('-')[-1])
        next_num = last_num + 1
    else:
        next_num = 1
    return f"{prefix}{next_num:04d}"


def apply_discount(subtotal, discount):
    """Calculate discount amount for a subtotal."""
    if discount is None:
        return Decimal('0.00')
    if discount.discount_type == 'percentage':
        return (subtotal * discount.value / Decimal('100')).quantize(Decimal('0.01'))
    else:
        return min(discount.value, subtotal)


def process_checkout(shift, cashier_id, items_data, payments_data,
                     discount_id=None, notes=''):
    """
    Process a sale atomically.

    Args:
        shift: The open Shift instance
        cashier_id: ID of the cashier user
        items_data: list of dicts with product_id, quantity, discount_id (optional)
        payments_data: list of dicts with payment_method, amount, reference (optional)
        discount_id: optional sale-level discount ID
        notes: optional sale notes

    Returns:
        The created Sale instance

    Raises:
        ValidationError on insufficient stock or payment
    """
    with transaction.atomic():
        # Resolve sale-level discount
        sale_discount = None
        if discount_id:
            try:
                sale_discount = Discount.objects.get(
                    pk=discount_id, is_active=True,
                )
            except Discount.DoesNotExist:
                raise ValidationError({'discount_id': 'Discount not found or inactive.'})

        subtotal = Decimal('0.00')
        tax_total = Decimal('0.00')
        item_discount_total = Decimal('0.00')
        sale_items = []

        for item_data in items_data:
            product = (
                Product.objects
                .select_for_update()
                .get(pk=item_data['product_id'], is_active=True)
            )
            quantity = Decimal(str(item_data['quantity']))

            # Check stock
            if product.track_stock and product.stock_quantity < quantity:
                raise ValidationError({
                    'items': f'Insufficient stock for {product.name}. '
                             f'Available: {product.stock_quantity}, '
                             f'Requested: {quantity}',
                })

            unit_price = product.selling_price
            line_subtotal = unit_price * quantity

            # Item-level discount
            item_discount = None
            item_discount_amount = Decimal('0.00')
            if item_data.get('discount_id'):
                try:
                    item_discount = Discount.objects.get(
                        pk=item_data['discount_id'], is_active=True,
                    )
                    item_discount_amount = apply_discount(line_subtotal, item_discount)
                except Discount.DoesNotExist:
                    pass

            discounted_subtotal = line_subtotal - item_discount_amount
            tax_amount = (
                discounted_subtotal * product.tax_rate / Decimal('100')
            ).quantize(Decimal('0.01'))
            line_total = discounted_subtotal + tax_amount

            subtotal += line_subtotal
            tax_total += tax_amount
            item_discount_total += item_discount_amount

            sale_items.append({
                'product': product,
                'product_name': product.name,
                'unit_price': unit_price,
                'quantity': quantity,
                'tax_rate': product.tax_rate,
                'tax_amount': tax_amount,
                'discount': item_discount,
                'discount_amount': item_discount_amount,
                'line_total': line_total,
            })

            # Deduct stock
            if product.track_stock:
                OutletStock, StockAuditLog = _get_inventory_models()
                qty_before = product.stock_quantity
                product.stock_quantity -= quantity
                product.save(update_fields=['stock_quantity', 'updated_at'])

                # Deduct from OutletStock
                outlet_stock, _ = OutletStock.objects.select_for_update().get_or_create(
                    outlet=shift.outlet, product=product,
                    defaults={'quantity': Decimal('0.000')},
                )
                outlet_stock.quantity -= quantity
                outlet_stock.save(update_fields=['quantity', 'updated_at'])

                sale_items[-1]['_stock_deducted'] = {
                    'qty_before': qty_before,
                    'qty_after': product.stock_quantity,
                }

        # Sale-level discount
        sale_discount_amount = apply_discount(subtotal - item_discount_total, sale_discount)
        discount_total = item_discount_total + sale_discount_amount
        grand_total = subtotal + tax_total - discount_total

        # Validate payments
        total_paid = sum(Decimal(str(p['amount'])) for p in payments_data)
        if total_paid < grand_total:
            raise ValidationError({
                'payments': f'Insufficient payment. Total: {grand_total}, '
                            f'Paid: {total_paid}',
            })

        # Create sale
        receipt_number = generate_receipt_number(shift.outlet_id)
        sale = Sale.objects.create(
            receipt_number=receipt_number,
            outlet=shift.outlet,
            shift=shift,
            cashier_id=cashier_id,
            subtotal=subtotal,
            tax_total=tax_total,
            discount_total=discount_total,
            grand_total=grand_total,
            discount=sale_discount,
            status='completed',
            notes=notes,
        )

        # Create sale items and audit logs
        OutletStock, StockAuditLog = _get_inventory_models()
        for item in sale_items:
            stock_info = item.pop('_stock_deducted', None)
            SaleItem.objects.create(sale=sale, **item)
            if stock_info:
                StockAuditLog.objects.create(
                    product=item['product'],
                    outlet=shift.outlet,
                    movement_type='sale',
                    quantity_change=-item['quantity'],
                    quantity_before=stock_info['qty_before'],
                    quantity_after=stock_info['qty_after'],
                    reference_type='Sale',
                    reference_id=sale.pk,
                    user_id=cashier_id,
                )

        # Create payments
        for payment_data in payments_data:
            Payment.objects.create(
                sale=sale,
                payment_method=payment_data['payment_method'],
                amount=Decimal(str(payment_data['amount'])),
                reference=payment_data.get('reference', ''),
            )

        # Create journal entry for the sale
        try:
            from finance.services import create_sale_journal_entry
            create_sale_journal_entry(sale)
        except Exception:
            logger.error(
                'Failed to create journal entry for sale %s',
                sale.receipt_number, exc_info=True,
            )

        # Submit for EFRIS fiscalization (non-blocking: failures are logged
        # but the sale still succeeds and is retried asynchronously)
        try:
            from fiscalization.services import submit_sale_for_fiscalization
            submit_sale_for_fiscalization(sale)
        except Exception:
            logger.error(
                'Failed to submit sale %s for fiscalization',
                sale.receipt_number, exc_info=True,
            )

        return sale
