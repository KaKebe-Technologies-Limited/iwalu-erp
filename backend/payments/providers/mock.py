"""
Mock payment provider for development, tests, and demos.

Resolves immediately to SUCCESS so the full sale → payment → fiscalization
flow can be exercised end-to-end without real provider credentials.

Special amount triggers (for testing failure paths):
    amount ending in .01 → FAILED
    amount ending in .02 → CANCELLED
    amount ending in .03 → EXPIRED
    amount ending in .99 → PROCESSING (stays in flight; query_status flips to SUCCESS)
"""
import uuid
from decimal import Decimal
from .base import PaymentProvider, PaymentResult, PaymentStatus


def _trigger_status(amount) -> PaymentStatus:
    """Map magic-number test amounts to specific terminal statuses."""
    cents = (Decimal(amount) * 100).to_integral_value() % 100
    return {
        1: PaymentStatus.FAILED,
        2: PaymentStatus.CANCELLED,
        3: PaymentStatus.EXPIRED,
        99: PaymentStatus.PROCESSING,
    }.get(int(cents), PaymentStatus.SUCCESS)


class MockProvider(PaymentProvider):
    name = 'mock'
    supported_methods = ('mobile_money', 'card', 'bank')

    def initiate_payment(self, transaction) -> PaymentResult:
        provider_txn_id = f'MOCK-{uuid.uuid4().hex[:12].upper()}'
        status = _trigger_status(transaction.amount)
        return PaymentResult(
            status=status,
            provider_transaction_id=provider_txn_id,
            provider_status_code=status.value.upper(),
            provider_status_message=f'Mock provider resolved as {status.value}.',
            raw_response={
                'provider': 'mock',
                'transaction_id': provider_txn_id,
                'amount': str(transaction.amount),
                'currency': transaction.currency,
                'phone_number': transaction.phone_number,
                'reference': transaction.reference,
                'resolved_status': status.value,
            },
        )

    def initiate_disbursement(self, transaction) -> PaymentResult:
        provider_txn_id = f'MOCK-DISB-{uuid.uuid4().hex[:12].upper()}'
        status = _trigger_status(transaction.amount)
        return PaymentResult(
            status=status,
            provider_transaction_id=provider_txn_id,
            provider_status_code=status.value.upper(),
            provider_status_message=f'Mock disbursement resolved as {status.value}.',
            raw_response={
                'provider': 'mock',
                'transaction_id': provider_txn_id,
                'amount': str(transaction.amount),
                'currency': transaction.currency,
                'phone_number': transaction.phone_number,
                'reference': transaction.reference,
                'resolved_status': status.value,
                'type': 'disbursement',
            },
        )

    def query_status(self, transaction) -> PaymentResult:
        # Anything stuck in PROCESSING flips to SUCCESS on the next query
        # so polling tests have a deterministic happy path.
        current = transaction.status
        if current == 'processing':
            new_status = PaymentStatus.SUCCESS
        else:
            new_status = PaymentStatus(current) if current in PaymentStatus._value2member_map_ else PaymentStatus.PROCESSING
        return PaymentResult(
            status=new_status,
            provider_transaction_id=transaction.provider_transaction_id,
            provider_status_code=new_status.value.upper(),
            provider_status_message=f'Mock query → {new_status.value}',
            raw_response={'provider': 'mock', 'queried': True},
        )

    def parse_callback(self, payload: dict) -> PaymentResult:
        status_str = (payload.get('status') or 'success').lower()
        try:
            status = PaymentStatus(status_str)
        except ValueError:
            status = PaymentStatus.FAILED
        return PaymentResult(
            status=status,
            provider_transaction_id=str(payload.get('transaction_id', '')),
            provider_status_code=status.value.upper(),
            provider_status_message='Mock callback received.',
            raw_response=payload,
        )
