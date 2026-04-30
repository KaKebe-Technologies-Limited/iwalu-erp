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


def handle_callback(provider_name: str, payload: dict, request=None) -> PaymentTransaction | None:
    """
    Handle a webhook callback from a provider.

    Security model:
      1. Parse the payload to find the transaction (parse_callback never
         mutates state).
      2. Refuse to act on transactions that already reached a terminal
         status — protects against replay attacks where an attacker resends
         a captured "SUCCESSFUL" payload.
      3. Refuse cross-provider callbacks (txn.provider must match).
      4. ALWAYS re-query the provider for authoritative status. We never
         trust the payload's claimed status, because for MTN/Airtel/Pesapal
         the callback body is forgeable by anyone who can reach our public
         webhook URL.
      5. After re-query, sanity-check that the provider's reported amount/
         currency match what we initiated; mismatch flips status to failed
         and logs an alert (signals tampering or provider misroute).
    """
    try:
        provider = get_provider(provider_name=provider_name)
        parsed = provider.parse_callback(payload)
    except Exception as exc:
        logger.exception('Failed to parse %s callback: %s', provider_name, exc)
        return None

    txn = _find_transaction_for_callback(provider_name, parsed, payload)
    if not txn:
        logger.warning('Callback for %s could not be matched to a transaction.', provider_name)
        return None

    # (3) Cross-provider callback — refuse.
    if txn.provider != provider_name:
        logger.warning(
            'Callback provider mismatch: txn=%s expected=%s got=%s',
            txn.reference, txn.provider, provider_name,
        )
        return None

    # (2) Replay protection.
    if txn.is_terminal:
        logger.info(
            'Ignoring callback for terminal txn %s (status=%s).',
            txn.reference, txn.status,
        )
        return txn

    txn.callback_payload = payload
    txn.save(update_fields=['callback_payload', 'updated_at'])

    # (4) Re-query the provider for the authoritative status. The callback
    # payload is treated purely as a "wake up and check" signal.
    try:
        authoritative = provider.query_status(txn)
    except (ProviderError, ProviderRejectedError) as exc:
        logger.warning('Post-callback query failed for %s: %s', txn.reference, exc)
        txn.error_message = f'Post-callback query error: {exc}'[:2000]
        txn.save(update_fields=['error_message', 'updated_at'])
        return txn
    except Exception as exc:
        logger.exception('Unexpected post-callback query error for %s', txn.reference)
        txn.error_message = f'Post-callback query error: {exc}'[:2000]
        txn.save(update_fields=['error_message', 'updated_at'])
        return txn

    # (5) Amount/currency tamper check on success.
    if authoritative.status == PaymentStatus.SUCCESS:
        raw = authoritative.raw_response or {}
        reported_amount = _extract_reported_amount(raw)
        reported_currency = _extract_reported_currency(raw)
        if reported_amount is not None and reported_amount != txn.amount:
            logger.error(
                'Amount mismatch on callback for %s: txn=%s reported=%s',
                txn.reference, txn.amount, reported_amount,
            )
            authoritative.status = PaymentStatus.FAILED
            authoritative.error_message = (
                f'Amount mismatch: expected {txn.amount}, provider reported {reported_amount}'
            )
        elif reported_currency and reported_currency != txn.currency:
            logger.error(
                'Currency mismatch on callback for %s: txn=%s reported=%s',
                txn.reference, txn.currency, reported_currency,
            )
            authoritative.status = PaymentStatus.FAILED
            authoritative.error_message = (
                f'Currency mismatch: expected {txn.currency}, got {reported_currency}'
            )

    _apply_result(txn, authoritative)
    return txn


def _extract_reported_amount(raw: dict):
    """Best-effort extraction of the provider-reported amount from query_status."""
    if not isinstance(raw, dict):
        return None
    # MTN: top-level "amount"; Airtel: data.transaction.amount;
    # Pesapal: amount or Amount.
    candidates = [
        raw.get('amount'),
        raw.get('Amount'),
        ((raw.get('data') or {}).get('transaction') or {}).get('amount'),
    ]
    for value in candidates:
        if value is None:
            continue
        try:
            return Decimal(str(value))
        except (ValueError, ArithmeticError):
            continue
    return None


def _extract_reported_currency(raw: dict):
    if not isinstance(raw, dict):
        return None
    return (
        raw.get('currency')
        or raw.get('Currency')
        or ((raw.get('data') or {}).get('transaction') or {}).get('currency')
        or None
    )


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
