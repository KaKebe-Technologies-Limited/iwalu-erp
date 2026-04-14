"""
Pesapal API v3 provider.

Stub implementation against Pesapal v3
(https://developer.pesapal.com/api3-demo-docs/api3-introduction). Pesapal is
a payment aggregator: a single integration handles cards (Visa/Mastercard),
mobile money (MTN/Airtel via their rails), and bank transfers. We use it
primarily as a card-payment rail and as a fallback when direct MTN/Airtel
APIs are unavailable.

Once you have:
    - consumer_key + consumer_secret (from pesapal.com merchant dashboard)
    - a registered IPN (Instant Payment Notification) URL → ipn_id
    - approved live credentials (sandbox base: cybqa.pesapal.com/pesapalv3)

...this should work end-to-end. Note: Pesapal does NOT directly debit the
customer; instead it returns a `redirect_url` that the cashier-facing UI
must open in a browser/iframe so the customer can complete payment.

Flow:
    1. POST /api/Auth/RequestToken            → bearer token (5 min lifetime)
    2. POST /api/Transactions/SubmitOrderRequest → returns redirect_url + order_tracking_id
    3. POST /api/Transactions/GetTransactionStatus → poll status by order_tracking_id
    4. IPN callback                           → final state
"""
import logging
import requests
from .base import (
    PaymentProvider, PaymentResult, PaymentStatus,
    ProviderError, ProviderRejectedError,
)

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 20


# Pesapal payment_status_description → canonical PaymentStatus
PESAPAL_STATUS_MAP = {
    'COMPLETED': PaymentStatus.SUCCESS,
    'FAILED': PaymentStatus.FAILED,
    'INVALID': PaymentStatus.FAILED,
    'REVERSED': PaymentStatus.FAILED,
    'PENDING': PaymentStatus.PROCESSING,
}


class PesapalProvider(PaymentProvider):
    name = 'pesapal'
    # Pesapal aggregates all three rails through one integration.
    supported_methods = ('card', 'mobile_money', 'bank')

    def __init__(self, config):
        super().__init__(config)
        if not config.pesapal_enabled:
            raise ProviderError('Pesapal provider selected but pesapal_enabled is False.')
        if not (config.pesapal_consumer_key and config.pesapal_consumer_secret):
            raise ProviderError(
                'Pesapal provider requires pesapal_consumer_key and '
                'pesapal_consumer_secret. Get them from the Pesapal merchant dashboard.'
            )
        if not config.pesapal_ipn_id:
            raise ProviderError(
                'Pesapal provider requires pesapal_ipn_id. Register your IPN '
                'URL via POST /api/URLSetup/RegisterIPN once and store the id.'
            )
        self.base_url = config.pesapal_base_url.rstrip('/')
        self.consumer_key = config.pesapal_consumer_key
        self.consumer_secret = config.pesapal_consumer_secret
        self.ipn_id = config.pesapal_ipn_id
        self.callback_url = config.pesapal_callback_url
        self._access_token = None

    # ----- helpers -----

    def _get_access_token(self) -> str:
        if self._access_token:
            return self._access_token
        url = f'{self.base_url}/api/Auth/RequestToken'
        try:
            resp = requests.post(
                url,
                json={
                    'consumer_key': self.consumer_key,
                    'consumer_secret': self.consumer_secret,
                },
                headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise ProviderError(f'Pesapal token request failed: {exc}') from exc

        if resp.status_code >= 500:
            raise ProviderError(f'Pesapal token 5xx: {resp.status_code}')
        if resp.status_code >= 400:
            raise ProviderRejectedError(
                f'Pesapal token rejected ({resp.status_code}): {resp.text[:300]}'
            )
        token = resp.json().get('token')
        if not token:
            raise ProviderError('Pesapal token response missing token.')
        self._access_token = token
        return token

    def _auth_headers(self) -> dict:
        return {
            'Authorization': f'Bearer {self._get_access_token()}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    # ----- public API -----

    def initiate_payment(self, transaction) -> PaymentResult:
        # Split customer name → first/last (Pesapal requires both)
        full_name = (transaction.customer_name or 'Customer').strip()
        parts = full_name.split(' ', 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else parts[0]

        body = {
            'id': transaction.reference,
            'currency': transaction.currency,
            'amount': float(transaction.amount),
            'description': (transaction.description or 'Payment')[:100],
            'callback_url': self.callback_url,
            'notification_id': self.ipn_id,
            'billing_address': {
                'email_address': transaction.customer_email or '',
                'phone_number': transaction.phone_number or '',
                'first_name': first_name,
                'last_name': last_name,
            },
        }

        url = f'{self.base_url}/api/Transactions/SubmitOrderRequest'
        try:
            resp = requests.post(
                url, json=body, headers=self._auth_headers(), timeout=DEFAULT_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise ProviderError(f'Pesapal submit failed: {exc}') from exc

        if resp.status_code >= 500:
            raise ProviderError(f'Pesapal 5xx: {resp.status_code}')
        if resp.status_code >= 400:
            raise ProviderRejectedError(
                f'Pesapal rejected ({resp.status_code}): {resp.text[:500]}'
            )

        data = resp.json()
        order_tracking_id = data.get('order_tracking_id', '')
        if not order_tracking_id:
            raise ProviderRejectedError(
                f'Pesapal response missing order_tracking_id: {data}'
            )

        return PaymentResult(
            status=PaymentStatus.PROCESSING,
            provider_transaction_id=order_tracking_id,
            provider_status_code='SUBMITTED',
            provider_status_message=(
                'Pesapal order created. Open redirect_url in browser/iframe '
                'to let the customer complete payment.'
            ),
            raw_response=data,  # contains 'redirect_url' for the UI to open
        )

    def initiate_disbursement(self, transaction) -> PaymentResult:
        raise ProviderError('Pesapal provider does not support direct disbursements.')

    def query_status(self, transaction) -> PaymentResult:
        order_tracking_id = transaction.provider_transaction_id
        if not order_tracking_id:
            raise ProviderRejectedError('No order_tracking_id to query.')

        url = (
            f'{self.base_url}/api/Transactions/GetTransactionStatus'
            f'?orderTrackingId={order_tracking_id}'
        )
        try:
            resp = requests.get(url, headers=self._auth_headers(), timeout=DEFAULT_TIMEOUT)
        except requests.RequestException as exc:
            raise ProviderError(f'Pesapal query failed: {exc}') from exc

        if resp.status_code >= 500:
            raise ProviderError(f'Pesapal query 5xx: {resp.status_code}')
        if resp.status_code >= 400:
            raise ProviderRejectedError(
                f'Pesapal query rejected ({resp.status_code}): {resp.text[:300]}'
            )

        data = resp.json()
        desc = (data.get('payment_status_description') or '').upper()
        canonical = PESAPAL_STATUS_MAP.get(desc, PaymentStatus.PROCESSING)
        return PaymentResult(
            status=canonical,
            provider_transaction_id=order_tracking_id,
            provider_status_code=desc,
            provider_status_message=data.get('description', '') or '',
            raw_response=data,
        )

    def parse_callback(self, payload: dict) -> PaymentResult:
        # Pesapal IPN sends OrderTrackingId + OrderMerchantReference; we then
        # have to call GetTransactionStatus to confirm the actual status.
        order_tracking_id = (
            payload.get('OrderTrackingId') or payload.get('order_tracking_id', '')
        )
        return PaymentResult(
            status=PaymentStatus.PROCESSING,  # caller must follow up with query_status
            provider_transaction_id=str(order_tracking_id),
            provider_status_code='IPN_RECEIVED',
            provider_status_message=(
                'Pesapal IPN received; caller must call query_status() to '
                'fetch the authoritative status.'
            ),
            raw_response=payload,
        )
