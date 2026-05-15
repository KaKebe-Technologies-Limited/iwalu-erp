import logging
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

from fuel.models import Pump
from inventory.models import OutletStock, StockAuditLog
from outlets.models import Outlet
from products.models import Category, Product
from sales.models import Discount, Sale, SaleItem, Payment, Shift
from sales.services import apply_discount, generate_receipt_number
from fiscalization.services import submit_sale_for_fiscalization
from users.permissions import IsCashierOrAbove

from .models import MobileSyncLog
from .permissions import IsMobileClient
from .serializers import (
    MobileBatchSyncSerializer,
    MobileCategorySerializer,
    MobileDiscountSerializer,
    MobileProductSerializer,
    MobilePumpSerializer,
)


class ShiftStartDataView(APIView):
    """
    GET /api/mobile/shift-start-data/?outlet_id=<id>

    Returns the complete offline data bundle a mobile client needs at shift
    start: outlet info, active products with outlet stock, categories,
    valid discounts, and active pumps.
    """
    permission_classes = [IsAuthenticated, IsMobileClient, IsCashierOrAbove]

    def get(self, request):
        outlet_id = request.query_params.get('outlet_id')
        if not outlet_id:
            return Response(
                {'error': 'outlet_id query parameter is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            outlet = Outlet.objects.get(pk=outlet_id)
        except Outlet.DoesNotExist:
            return Response(
                {'error': 'Outlet not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Verify the requesting user has an open shift at this outlet
        if not Shift.objects.filter(
            user_id=request.user.id, status='open', outlet_id=outlet_id
        ).exists():
            return Response(
                {'error': 'No open shift for this outlet.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        products_qs = Product.objects.filter(
            is_active=True
        ).select_related('category')

        outlet_stock_qs = OutletStock.objects.filter(
            outlet_id=outlet_id
        ).select_related('product')
        outlet_stock_map = {
            os.product_id: os.quantity for os in outlet_stock_qs
        }

        categories = Category.objects.filter(is_active=True)

        now = timezone.now()
        discounts = Discount.objects.filter(is_active=True).filter(
            Q(valid_until__isnull=True) | Q(valid_until__gt=now)
        )

        pumps = Pump.objects.filter(outlet_id=outlet_id, status='active')

        product_data = MobileProductSerializer(
            products_qs,
            many=True,
            context={'outlet_stock_map': outlet_stock_map},
        ).data

        payload = {
            'outlet': {
                'id': outlet.id,
                'name': outlet.name,
                'outlet_type': getattr(outlet, 'outlet_type', None),
            },
            'products': product_data,
            'categories': MobileCategorySerializer(categories, many=True).data,
            'discounts': MobileDiscountSerializer(discounts, many=True).data,
            'pumps': MobilePumpSerializer(pumps, many=True).data,
            'generated_at': now.isoformat(),
        }

        return Response(payload, status=status.HTTP_200_OK)


class MobileSyncRateThrottle(UserRateThrottle):
    scope = 'mobile-sync'


class MobileSyncView(APIView):
    """
    POST /api/mobile/sync/

    Accepts a batch of up to 500 offline transactions, creates Sale records,
    deducts stock, triggers fiscalization, and returns per-transaction results.

    Idempotent: transactions with a previously-seen client_uuid return
    status='duplicate' without creating a second Sale.
    """
    permission_classes = [IsAuthenticated, IsMobileClient, IsCashierOrAbove]
    throttle_classes = [MobileSyncRateThrottle]

    def post(self, request):
        from django.db import transaction as db_transaction

        serializer = MobileBatchSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        shift_id = data['shift_id']
        device_id = data['device_id']
        transactions = data['transactions']

        try:
            shift = Shift.objects.get(pk=shift_id)
        except Shift.DoesNotExist:
            return Response(
                {'error': 'Shift not found.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if shift.status != 'open':
            return Response(
                {'error': 'Shift is not open.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if shift.user_id != request.user.id:
            return Response(
                {'error': 'Shift does not belong to the authenticated user.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        transactions_sorted = sorted(transactions, key=lambda t: t['created_at'])

        results = []
        success_count = 0
        failed_count = 0

        for txn in transactions_sorted:
            client_uuid = txn['client_uuid']

            existing = Sale.objects.filter(client_uuid=client_uuid).first()
            if existing:
                results.append({
                    'client_uuid': client_uuid,
                    'status': 'duplicate',
                    'sale_id': existing.id,
                    'receipt_number': existing.receipt_number,
                    'message': 'Transaction already synced.',
                })
                continue

            try:
                with db_transaction.atomic():
                    result = self._create_sale(
                        txn=txn,
                        shift=shift,
                        user=request.user,
                        client_uuid=client_uuid,
                    )
                results.append(result)
                success_count += 1
            except ValueError as exc:
                failed_count += 1
                results.append({
                    'client_uuid': client_uuid,
                    'status': 'failed',
                    'sale_id': None,
                    'receipt_number': None,
                    'message': str(exc),
                })
            except Exception as exc:
                logger.error(
                    'Mobile sync internal error for uuid %s', client_uuid, exc_info=True
                )
                failed_count += 1
                results.append({
                    'client_uuid': client_uuid,
                    'status': 'failed',
                    'sale_id': None,
                    'receipt_number': None,
                    'message': 'Internal error processing transaction.',
                })

        MobileSyncLog.objects.create(
            device_id=device_id,
            shift_id=shift_id,
            user_id=request.user.id,
            outlet_id=shift.outlet_id,
            transaction_count=len(transactions_sorted),
            success_count=success_count,
            failed_count=failed_count,
            ip_address=request.META.get('REMOTE_ADDR'),
        )

        return Response(
            {
                'processed': len(transactions_sorted),
                'results': results,
            },
            status=status.HTTP_200_OK,
        )

    def _create_sale(self, *, txn, shift, user, client_uuid):
        """
        Creates a single Sale, SaleItems, Payments, deducts stock,
        creates audit logs, and triggers fiscalization.
        Raises on any validation failure — caller wraps in atomic().
        """
        items_data = txn['items']
        payments_data = txn['payments']

        subtotal = Decimal('0.00')
        tax_total = Decimal('0.00')
        discount_total = Decimal('0.00')
        sale_items_to_create = []

        for item_data in items_data:
            product = Product.objects.select_for_update().get(pk=item_data['product_id'])
            if not product.is_active:
                raise ValueError(
                    f"Product '{product.name}' (id={product.id}) is inactive."
                )

            quantity = item_data['quantity']
            unit_price = item_data['unit_price']

            if product.track_stock:
                if product.stock_quantity < quantity:
                    raise ValueError(
                        f"Insufficient stock for '{product.name}'. "
                        f"Available: {product.stock_quantity}, requested: {quantity}."
                    )

            line_subtotal = unit_price * quantity
            item_discount_amount = Decimal('0.00')

            if item_data.get('discount_id'):
                try:
                    item_discount = Discount.objects.get(
                        pk=item_data['discount_id'], is_active=True
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
            discount_total += item_discount_amount

            sale_items_to_create.append({
                'product': product,
                'product_name': product.name,
                'unit_price': unit_price,
                'quantity': quantity,
                'tax_rate': product.tax_rate,
                'tax_amount': tax_amount,
                'discount_id': item_data.get('discount_id'),
                'discount_amount': item_discount_amount,
                'line_total': line_total,
            })

        grand_total = subtotal + tax_total - discount_total

        total_paid = sum(p['amount'] for p in payments_data)
        if total_paid < grand_total:
            raise ValueError(
                f"Insufficient payment. Grand total: {grand_total}, "
                f"total paid: {total_paid}."
            )

        receipt_number = generate_receipt_number(shift.outlet_id)
        sale = Sale.objects.create(
            outlet=shift.outlet,
            shift=shift,
            cashier_id=user.id,
            subtotal=subtotal,
            tax_total=tax_total,
            discount_total=discount_total,
            grand_total=grand_total,
            receipt_number=receipt_number,
            notes=txn.get('notes', ''),
            status='completed',
            client_uuid=client_uuid,
            source='mobile',
        )

        for item_data in sale_items_to_create:
            SaleItem.objects.create(
                sale=sale,
                product=item_data['product'],
                product_name=item_data['product_name'],
                unit_price=item_data['unit_price'],
                quantity=item_data['quantity'],
                tax_rate=item_data['tax_rate'],
                tax_amount=item_data['tax_amount'],
                discount_id=item_data['discount_id'],
                discount_amount=item_data['discount_amount'],
                line_total=item_data['line_total'],
            )

        for p in payments_data:
            Payment.objects.create(
                sale=sale,
                payment_method=p['payment_method'],
                amount=p['amount'],
                reference=p.get('reference', ''),
            )

        for item_data in sale_items_to_create:
            product = item_data['product']
            qty = item_data['quantity']
            if product.track_stock:
                qty_before = product.stock_quantity
                product.stock_quantity -= qty
                product.save(update_fields=['stock_quantity'])

                try:
                    outlet_stock = OutletStock.objects.select_for_update().get(
                        outlet_id=shift.outlet_id, product=product
                    )
                    outlet_stock.quantity -= qty
                    outlet_stock.save(update_fields=['quantity'])
                except OutletStock.DoesNotExist:
                    pass

                StockAuditLog.objects.create(
                    product=product,
                    outlet=shift.outlet,
                    movement_type='sale',
                    quantity_change=-qty,
                    quantity_before=qty_before,
                    quantity_after=product.stock_quantity,
                    reference_type='sale',
                    reference_id=sale.id,
                    user_id=user.id,
                    notes=f'Mobile sync — receipt {receipt_number}',
                )

        try:
            submit_sale_for_fiscalization(sale)
        except Exception:
            logger.error('Fiscalization failed for sale %s (mobile sync)', sale.id, exc_info=True)

        return {
            'client_uuid': client_uuid,
            'status': 'synced',
            'sale_id': sale.id,
            'receipt_number': receipt_number,
            'message': None,
        }
