"""
Payments services.

High-level flow:
    1. Cashier calls initiate_payment(...) or initiate_disbursement(...)
    2. We pick the configured provider, create a PaymentTransaction row,
       and call provider.initiate_payment() or provider.initiate_disbursement().
    3. For mock → returns SUCCESS immediately.
       For MTN/Airtel → returns PROCESSING; final state arrives via
       callback or follow-up query_status().
       For Pesapal → returns PROCESSING + redirect_url for the UI to open.
    4. Webhooks land at /api/payments/callback/<provider>/ and call
       handle_callback() which advances the transaction to its final state.
    5. Polling jobs / manual "check status" calls reconcile via query_status.

Always returns a PaymentTransaction row (never raises ProviderError to the
caller). Inspect `.status` and `.error_message` for outcome.
"""
import logging
import secrets
from decimal import Decimal
from django.db import transaction as db_transaction
from django.utils import timezone

from .models import PaymentConfig, PaymentTransaction
from .providers import (
    get_provider_class, PaymentStatus,
    ProviderError, ProviderRejectedError,
)

logger = logging.getLogger(__name__)


def get_config():
    """Return the tenant's PaymentConfig, creating defaults on first access."""
    config, _ = PaymentConfig.objects.get_or_create(pk=1)
    return config


def get_provider(provider_name=None, config=None):
    """Instantiate a provider. Defaults to config.default_provider."""
    cfg = config or get_config()
    name = provider_name or cfg.default_provider
    provider_cls = get_provider_class(name)
    return provider_cls(cfg)


def _generate_reference(prefix='PAY') -> str:
    """Generate a unique merchant transaction reference."""
    return f'{prefix}-{secrets.token_hex(8).upper()}'


def initiate_payment(
    *,
    amount,
    method: str,
    provider_name: str | None = None,
    phone_number: str = '',
    customer_email: str = '',
    customer_name: str = '',
    description: str = '',
    sale=None,
    initiated_by_id: int | None = None,
    currency: str | None = None,
) -> PaymentTransaction:
    """
    Initiate a collection (request money from customer).
    """
    return _initiate(
        transaction_type='collection',
        amount=amount,
        method=method,
        provider_name=provider_name,
        phone_number=phone_number,
        customer_email=customer_email,
        customer_name=customer_name,
        description=description,
        sale=sale,
        initiated_by_id=initiated_by_id,
        currency=currency,
    )


def initiate_disbursement(
    *,
    amount,
    method: str,
    provider_name: str | None = None,
    phone_number: str = '',
    customer_email: str = '',
    customer_name: str = '',
    description: str = '',
    sale=None,
    initiated_by_id: int | None = None,
    currency: str | None = None,
) -> PaymentTransaction:
    """
    Initiate a disbursement (send money to someone).
    """
    return _initiate(
        transaction_type='disbursement',
        amount=amount,
        method=method,
        provider_name=provider_name,
        phone_number=phone_number,
        customer_email=customer_email,
        customer_name=customer_name,
        description=description,
        sale=sale,
        initiated_by_id=initiated_by_id,
        currency=currency,
    )


def _initiate(
    *,
    transaction_type: str,
    amount,
    method: str,
    provider_name: str | None = None,
    phone_number: str = '',
    customer_email: str = '',
    customer_name: str = '',
    description: str = '',
    sale=None,
    initiated_by_id: int | None = None,
    currency: str | None = None,
) -> PaymentTransaction:
    config = get_config()
    prefix = 'PAY' if transaction_type == 'collection' else 'DISB'

    if not config.is_enabled:
        return PaymentTransaction.objects.create(
            sale=sale,
            transaction_type=transaction_type,
            provider=provider_name or config.default_provider,
            method=method,
            amount=Decimal(amount),
            currency=currency or config.default_currency,
            phone_number=phone_number,
            customer_email=customer_email,
            customer_name=customer_name,
            description=description,
            reference=_generate_reference(prefix),
            status='failed',
            error_message='Payments are disabled in PaymentConfig.',
            initiated_by=initiated_by_id,
        )

    txn = PaymentTransaction.objects.create(
        sale=sale,
        transaction_type=transaction_type,
        provider=provider_name or config.default_provider,
        method=method,
        amount=Decimal(amount),
        currency=currency or config.default_currency,
        phone_number=phone_number,
        customer_email=customer_email,
        customer_name=customer_name,
        description=description,
        reference=_generate_reference(prefix),
        status='pending',
        initiated_by=initiated_by_id,
        initiated_at=timezone.now(),
    )

    try:
        provider = get_provider(provider_name=txn.provider, config=config)
    except ProviderError as exc:
        txn.status = 'failed'
        txn.error_message = f'Provider init error: {exc}'[:2000]
        txn.save(update_fields=['status', 'error_message', 'updated_at'])
        return txn

    # Validate method support
    if method not in provider.supported_methods:
        txn.status = 'failed'
        txn.error_message = (
            f'Provider {provider.name} does not support method "{method}". '
            f'Supported: {list(provider.supported_methods)}'
        )
        txn.save(update_fields=['status', 'error_message', 'updated_at'])
        return txn

    try:
        if transaction_type == 'disbursement':
            result = provider.initiate_disbursement(txn)
        else:
            result = provider.initiate_payment(txn)
    except ProviderRejectedError as exc:
        logger.warning('Payment %s rejected by %s: %s', txn.reference, provider.name, exc)
        txn.status = 'failed'
        txn.error_message = str(exc)[:2000]
        txn.save(update_fields=['status', 'error_message', 'updated_at'])
        return txn
    except ProviderError as exc:
        logger.warning('Payment %s transient failure on %s: %s',
                       txn.reference, provider.name, exc)
        txn.status = 'failed'
        txn.error_message = str(exc)[:2000]
        txn.save(update_fields=['status', 'error_message', 'updated_at'])
        return txn
    except Exception as exc:
        logger.exception('Unexpected payment error for %s', txn.reference)
        txn.status = 'failed'
        txn.error_message = f'Unexpected: {exc}'[:2000]
        txn.save(update_fields=['status', 'error_message', 'updated_at'])
        return txn

    _apply_result(txn, result)
    return txn


def query_payment_status(txn: PaymentTransaction) -> PaymentTransaction:
    """Poll provider for the latest status of an in-flight payment."""
    if txn.is_terminal:
        return txn
    try:
        provider = get_provider(provider_name=txn.provider)
        result = provider.query_status(txn)
    except (ProviderError, ProviderRejectedError) as exc:
        txn.error_message = str(exc)[:2000]
        txn.save(update_fields=['error_message', 'updated_at'])
        return txn
    except Exception as exc:
        logger.exception('Unexpected query error for %s', txn.reference)
        txn.error_message = f'Unexpected query error: {exc}'[:2000]
        txn.save(update_fields=['error_message', 'updated_at'])
        return txn

    _apply_result(txn, result)
    return txn


def handle_callback(provider_name: str, payload: dict) -> PaymentTransaction | None:
    """
    Handle a webhook callback from a provider.
    """
    try:
        provider = get_provider(provider_name=provider_name)
        result = provider.parse_callback(payload)
    except Exception as exc:
        logger.exception('Failed to parse %s callback: %s', provider_name, exc)
        return None

    txn = _find_transaction_for_callback(provider_name, result, payload)
    if not txn:
        logger.warning(
            'Callback for %s could not be matched to a transaction. payload=%s',
            provider_name, payload,
        )
        return None

    txn.callback_payload = payload

    # Pesapal IPNs only tell us "something happened" — we still need to
    # actively query for the authoritative status.
    if provider_name == 'pesapal':
        try:
            result = provider.query_status(txn)
        except Exception as exc:
            logger.exception('Pesapal post-IPN query failed for %s', txn.reference)
            txn.error_message = f'Post-IPN query error: {exc}'[:2000]
            txn.save()
            return txn

    _apply_result(txn, result)
    return txn


def _find_transaction_for_callback(provider_name, result, payload):
    """Look up a PaymentTransaction matching a callback."""
    qs = PaymentTransaction.objects.filter(provider=provider_name)
    if result.provider_transaction_id:
        match = qs.filter(provider_transaction_id=result.provider_transaction_id).first()
        if match:
            return match
    # Fall back to reference / externalId / OrderMerchantReference
    ref = (
        payload.get('externalId')
        or payload.get('OrderMerchantReference')
        or payload.get('reference')
    )
    if ref:
        return qs.filter(reference=ref).first()
    return None


@db_transaction.atomic
def _apply_result(txn: PaymentTransaction, result) -> None:
    """Apply a PaymentResult to a PaymentTransaction and persist."""
    txn.status = result.status.value
    if result.provider_transaction_id:
        txn.provider_transaction_id = result.provider_transaction_id
    txn.provider_status_code = result.provider_status_code or txn.provider_status_code
    txn.provider_status_message = (
        result.provider_status_message or txn.provider_status_message
    )
    if result.raw_response:
        txn.response_payload = result.raw_response
    if result.is_terminal:
        txn.completed_at = timezone.now()
    if result.status == PaymentStatus.FAILED and result.error_message:
        txn.error_message = result.error_message[:2000]
    txn.save()
