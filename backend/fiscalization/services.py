"""
Fiscalization services.

High-level flow:
    1. sales.process_checkout() calls submit_sale_for_fiscalization(sale)
    2. That builds a payload, picks the configured provider, and submits
    3. On success → FiscalInvoice.status = 'accepted' with fdn/qr_code
    4. On transient failure → status = 'failed', retry_count incremented,
       later picked up by retry_failed_invoices()
    5. On permanent rejection → status = 'rejected', no retry
    6. If fiscalization is disabled → status = 'skipped'

The sales flow never raises if fiscalization fails — the sale is still
recorded. Fiscal data appears on the receipt only after successful
submission.
"""
import logging
from django.utils import timezone

from .models import EfrisConfig, FiscalInvoice
from .providers import (
    get_provider_class, ProviderError, ProviderRejectedError,
)

logger = logging.getLogger(__name__)

MAX_RETRY_ATTEMPTS = 5


def get_config():
    """Return the tenant's EfrisConfig, creating defaults on first access."""
    config, _ = EfrisConfig.objects.get_or_create(pk=1)
    return config


def get_provider(config=None):
    """Instantiate the currently-configured provider."""
    cfg = config or get_config()
    provider_cls = get_provider_class(cfg.provider)
    return provider_cls(cfg)


def build_payload(sale, config):
    """
    Convert a sales.Sale into the canonical EFRIS payload shape.

    This is the provider-agnostic representation. Each provider may map
    fields to its own schema, but the content is the same.
    """
    items = []
    for item in sale.items.select_related('product').all():
        items.append({
            'code': item.product.sku if item.product else '',
            'name': item.product_name,
            'quantity': str(item.quantity),
            'unitPrice': str(item.unit_price),
            'taxRate': str(item.tax_rate),
            'taxAmount': str(item.tax_amount),
            'discountAmount': str(item.discount_amount),
            'lineTotal': str(item.line_total),
        })

    payment_methods = [
        {'method': p.payment_method, 'amount': str(p.amount)}
        for p in sale.payments.all()
    ]

    return {
        'invoiceReference': sale.receipt_number,
        'invoiceDate': sale.created_at.isoformat(),
        'currency': config.default_currency,
        'seller': {
            'tin': config.tin,
            'legalName': config.legal_name,
            'tradeName': config.trade_name,
        },
        'buyer': {
            # Walk-in customer; EFRIS accepts "Final Consumer" for retail
            'type': 'FINAL_CONSUMER',
            'tin': '',
            'name': 'Final Consumer',
        },
        'items': items,
        'totals': {
            'subtotal': str(sale.subtotal),
            'taxTotal': str(sale.tax_total),
            'discountTotal': str(sale.discount_total),
            'grandTotal': str(sale.grand_total),
        },
        'payments': payment_methods,
    }


def submit_sale_for_fiscalization(sale):
    """
    Submit a sale to EFRIS. Called from sales.process_checkout after the
    sale has been committed.

    Always returns a FiscalInvoice row (never raises). Check `.status` to
    see the outcome.
    """
    config = get_config()

    # 1. Fiscalization disabled → record skipped invoice
    if not config.is_enabled:
        return FiscalInvoice.objects.create(
            sale=sale,
            status='skipped',
            provider=config.provider,
            error_message='Fiscalization disabled in EfrisConfig.',
        )

    # 2. Build payload
    try:
        payload = build_payload(sale, config)
    except Exception as exc:
        logger.exception('Failed to build EFRIS payload for sale %s', sale.pk)
        return FiscalInvoice.objects.create(
            sale=sale,
            status='failed',
            provider=config.provider,
            error_message=f'Payload build error: {exc}',
        )

    # 3. Create the FiscalInvoice row first (so we have a trail even on crash)
    fiscal_invoice = FiscalInvoice.objects.create(
        sale=sale,
        status='submitted',
        provider=config.provider,
        request_payload=payload,
        submitted_at=timezone.now(),
    )

    # 4. Submit via provider
    try:
        provider = get_provider(config)
        result = provider.submit_invoice(payload)
    except ProviderRejectedError as exc:
        logger.warning('EFRIS rejected sale %s: %s', sale.pk, exc)
        fiscal_invoice.status = 'rejected'
        fiscal_invoice.error_message = str(exc)[:2000]
        fiscal_invoice.save(update_fields=['status', 'error_message', 'updated_at'])
        return fiscal_invoice
    except ProviderError as exc:
        logger.warning('EFRIS transient failure for sale %s: %s', sale.pk, exc)
        fiscal_invoice.status = 'failed'
        fiscal_invoice.error_message = str(exc)[:2000]
        fiscal_invoice.save(update_fields=['status', 'error_message', 'updated_at'])
        return fiscal_invoice
    except Exception as exc:
        logger.exception('Unexpected EFRIS error for sale %s', sale.pk)
        fiscal_invoice.status = 'failed'
        fiscal_invoice.error_message = f'Unexpected: {exc}'[:2000]
        fiscal_invoice.save(update_fields=['status', 'error_message', 'updated_at'])
        return fiscal_invoice

    # 5. Success → store fiscal data
    fiscal_invoice.status = 'accepted' if result.success else 'rejected'
    fiscal_invoice.fdn = result.fdn
    fiscal_invoice.invoice_id = result.invoice_id
    fiscal_invoice.verification_code = result.verification_code
    fiscal_invoice.qr_code = result.qr_code
    fiscal_invoice.response_payload = result.raw_response
    fiscal_invoice.accepted_at = timezone.now()
    fiscal_invoice.save()
    return fiscal_invoice


def retry_failed_invoices(limit=100):
    """
    Retry submissions for FiscalInvoices in 'failed' status.

    Designed to be called from a cron job or management command. Skips
    invoices that have hit MAX_RETRY_ATTEMPTS.
    """
    stats = {'retried': 0, 'succeeded': 0, 'still_failing': 0, 'exhausted': 0}

    qs = FiscalInvoice.objects.filter(
        status='failed', retry_count__lt=MAX_RETRY_ATTEMPTS,
    ).select_related('sale')[:limit]

    for fiscal_invoice in qs:
        stats['retried'] += 1
        fiscal_invoice.retry_count += 1

        try:
            config = get_config()
            provider = get_provider(config)
            result = provider.submit_invoice(fiscal_invoice.request_payload)
        except ProviderRejectedError as exc:
            fiscal_invoice.status = 'rejected'
            fiscal_invoice.error_message = str(exc)[:2000]
            fiscal_invoice.save()
            stats['still_failing'] += 1
            continue
        except ProviderError as exc:
            fiscal_invoice.error_message = str(exc)[:2000]
            if fiscal_invoice.retry_count >= MAX_RETRY_ATTEMPTS:
                stats['exhausted'] += 1
            fiscal_invoice.save()
            stats['still_failing'] += 1
            continue
        except Exception as exc:
            logger.exception('Retry error for FiscalInvoice %s', fiscal_invoice.pk)
            fiscal_invoice.error_message = f'Unexpected: {exc}'[:2000]
            fiscal_invoice.save()
            stats['still_failing'] += 1
            continue

        fiscal_invoice.status = 'accepted' if result.success else 'rejected'
        fiscal_invoice.fdn = result.fdn
        fiscal_invoice.invoice_id = result.invoice_id
        fiscal_invoice.verification_code = result.verification_code
        fiscal_invoice.qr_code = result.qr_code
        fiscal_invoice.response_payload = result.raw_response
        fiscal_invoice.accepted_at = timezone.now()
        fiscal_invoice.error_message = ''
        fiscal_invoice.save()
        stats['succeeded'] += 1

    return stats


def get_fiscal_data(sale):
    """
    Return receipt-ready fiscal data for a sale, or None if not fiscalized.

    Called by receipt generation. The frontend/receipt template displays
    the FDN, verification code, and QR code at the bottom of the receipt
    when present.
    """
    try:
        fi = sale.fiscal_invoice
    except FiscalInvoice.DoesNotExist:
        return None

    if not fi.is_fiscalized:
        return None

    return {
        'fdn': fi.fdn,
        'invoice_id': fi.invoice_id,
        'verification_code': fi.verification_code,
        'qr_code': fi.qr_code,
        'accepted_at': fi.accepted_at.isoformat() if fi.accepted_at else None,
    }
