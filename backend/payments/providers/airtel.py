"""
Airtel Money Collections and Disbursements API provider.

Direct integration against Airtel Africa OpenAPI.
"""
import logging
import requests
from .base import (
    PaymentProvider, PaymentResult, PaymentStatus,
    ProviderError, ProviderRejectedError,
)

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 20


AIRTEL_STATUS_MAP = {
    'TS': PaymentStatus.SUCCESS,        # Transaction Successful
    'TF': PaymentStatus.FAILED,         # Transaction Failed
    'TA': PaymentStatus.PROCESSING,     # Transaction Ambiguous
    'TIP': PaymentStatus.PROCESSING,    # Transaction In Progress
    'TE': PaymentStatus.EXPIRED,        # Transaction Expired
}


class AirtelProvider(PaymentProvider):
    name = 'airtel'
    supported_methods = ('mobile_money',)

    def __init__(self, config):
        super().__init__(config)
        self.base_url = config.airtel_base_url.rstrip('/')
        self.client_id = config.airtel_client_id
        self.client_secret = config.airtel_client_secret
        self.country = config.airtel_country or 'UG'
        self.currency = config.airtel_currency or 'UGX'
        
        # Disbursement credentials
        self.disb_client_id = config.airtel_disbursement_client_id or self.client_id
        self.disb_client_secret = config.airtel_disbursement_client_secret or self.client_secret
        
        self._tokens = {}

    def _get_access_token(self, product='collection') -> str:
        if product in self._tokens:
            return self._tokens[product]
            
        url = f'{self.base_url}/auth/oauth2/token'
        client_id = self.disb_client_id if product == 'disbursement' else self.client_id
        client_secret = self.disb_client_secret if product == 'disbursement' else self.client_secret
        
        if not (client_id and client_secret):
            raise ProviderError(f'Airtel {product} credentials missing.')

        try:
            resp = requests.post(
                url,
                json={
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'grant_type': 'client_credentials',
                },
                headers={'Content-Type': 'application/json', 'Accept': '*/*'},
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise ProviderError(f'Airtel {product} token request failed: {exc}') from exc

        if resp.status_code >= 400:
            raise ProviderError(f'Airtel {product} token error ({resp.status_code}): {resp.text[:300]}')
            
        token = resp.json().get('access_token')
        self._tokens[product] = token
        return token

    def _auth_headers(self, product='collection') -> dict:
        return {
            'Authorization': f'Bearer {self._get_access_token(product)}',
            'X-Country': self.country,
            'X-Currency': self.currency,
            'Content-Type': 'application/json',
            'Accept': '*/*',
        }

    @staticmethod
    def _strip_country_code(msisdn: str) -> str:
        s = msisdn.lstrip('+')
        if s.startswith('256'):
            return s[3:]
        return s

    def initiate_payment(self, transaction) -> PaymentResult:
        if not self.config.airtel_enabled:
            raise ProviderError('Airtel collections disabled.')

        body = {
            'reference': transaction.reference,
            'subscriber': {
                'country': self.country,
                'currency': self.currency,
                'msisdn': self._strip_country_code(transaction.phone_number),
            },
            'transaction': {
                'amount': str(transaction.amount),
                'country': self.country,
                'currency': self.currency,
                'id': transaction.reference,
            },
        }

        url = f'{self.base_url}/merchant/v1/payments/'
        try:
            resp = requests.post(
                url, json=body, headers=self._auth_headers(product='collection'), timeout=DEFAULT_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise ProviderError(f'Airtel collection failed: {exc}') from exc

        if resp.status_code >= 400:
            raise ProviderRejectedError(f'Airtel collection rejected ({resp.status_code}): {resp.text[:500]}')

        data = resp.json()
        airtel_txn = (data.get('data') or {}).get('transaction') or {}
        airtel_id = str(airtel_txn.get('id') or transaction.reference)

        return PaymentResult(
            status=PaymentStatus.PROCESSING,
            provider_transaction_id=airtel_id,
            provider_status_code=str(airtel_txn.get('status', 'PENDING')),
            provider_status_message='Airtel USSD push sent.',
            raw_response=data,
        )

    def initiate_disbursement(self, transaction) -> PaymentResult:
        if not self.config.airtel_disbursement_enabled:
            raise ProviderError('Airtel disbursements disabled.')

        body = {
            'reference': transaction.reference,
            'subscriber': {
                'country': self.country,
                'currency': self.currency,
                'msisdn': self._strip_country_code(transaction.phone_number),
            },
            'transaction': {
                'amount': str(transaction.amount),
                'country': self.country,
                'currency': self.currency,
                'id': transaction.reference,
            },
        }

        # Airtel disbursement endpoint (typical pattern)
        url = f'{self.base_url}/standard/v1/disbursements/'
        try:
            resp = requests.post(
                url, json=body, headers=self._auth_headers(product='disbursement'), timeout=DEFAULT_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise ProviderError(f'Airtel disbursement failed: {exc}') from exc

        if resp.status_code >= 400:
            raise ProviderRejectedError(f'Airtel disbursement rejected ({resp.status_code}): {resp.text[:500]}')

        data = resp.json()
        airtel_txn = (data.get('data') or {}).get('transaction') or {}
        airtel_id = str(airtel_txn.get('id') or transaction.reference)

        return PaymentResult(
            status=PaymentStatus.PROCESSING,
            provider_transaction_id=airtel_id,
            provider_status_code=str(airtel_txn.get('status', 'PENDING')),
            provider_status_message='Airtel disbursement initiated.',
            raw_response=data,
        )

    def query_status(self, transaction) -> PaymentResult:
        ref = transaction.provider_transaction_id or transaction.reference
        product = 'disbursement' if transaction.transaction_type == 'disbursement' else 'collection'
        endpoint = 'disbursements' if product == 'disbursement' else 'payments'
        
        url = f'{self.base_url}/standard/v1/{endpoint}/{ref}'
        try:
            resp = requests.get(url, headers=self._auth_headers(product=product), timeout=DEFAULT_TIMEOUT)
        except requests.RequestException as exc:
            raise ProviderError(f'Airtel query failed: {exc}') from exc

        if resp.status_code >= 400:
            raise ProviderRejectedError(f'Airtel query rejected ({resp.status_code}): {resp.text[:300]}')

        data = resp.json()
        txn = ((data.get('data') or {}).get('transaction')) or {}
        code = str(txn.get('status', '') or '').upper()
        canonical = AIRTEL_STATUS_MAP.get(code, PaymentStatus.PROCESSING)
        return PaymentResult(
            status=canonical,
            provider_transaction_id=ref,
            provider_status_code=code,
            provider_status_message=txn.get('message', '') or '',
            raw_response=data,
        )

    def parse_callback(self, payload: dict) -> PaymentResult:
        txn = payload.get('transaction') or {}
        code = str(txn.get('status_code', '') or txn.get('status', '') or '').upper()
        canonical = AIRTEL_STATUS_MAP.get(code, PaymentStatus.PROCESSING)
        return PaymentResult(
            status=canonical,
            provider_transaction_id=str(txn.get('id', '')),
            provider_status_code=code,
            provider_status_message=txn.get('message', '') or '',
            raw_response=payload,
        )
