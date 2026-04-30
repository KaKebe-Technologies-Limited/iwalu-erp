"""
MTN Mobile Money Collections and Disbursements API provider.

Direct integration against MTN MoMo API.
"""
import logging
import uuid
import requests
from .base import (
    PaymentProvider, PaymentResult, PaymentStatus,
    ProviderError, ProviderRejectedError,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 20


MTN_STATUS_MAP = {
    'SUCCESSFUL': PaymentStatus.SUCCESS,
    'FAILED': PaymentStatus.FAILED,
    'PENDING': PaymentStatus.PROCESSING,
    'REJECTED': PaymentStatus.FAILED,
    'TIMEOUT': PaymentStatus.EXPIRED,
}


class MTNProvider(PaymentProvider):
    name = 'mtn'
    supported_methods = ('mobile_money',)

    def __init__(self, config):
        super().__init__(config)
        self.base_url = config.mtn_base_url.rstrip('/')
        self.subscription_key = config.mtn_subscription_key
        self.api_user = config.mtn_api_user
        self.api_key = config.mtn_api_key
        self.target_environment = config.mtn_target_environment or 'sandbox'
        
        # Disbursement credentials
        self.disb_subscription_key = config.mtn_disbursement_subscription_key or self.subscription_key
        self.disb_api_user = config.mtn_disbursement_api_user or self.api_user
        self.disb_api_key = config.mtn_disbursement_api_key or self.api_key
        
        self._tokens = {}  # Cache tokens per product

    def _get_access_token(self, product='collection') -> str:
        if product in self._tokens:
            return self._tokens[product]
        
        url = f'{self.base_url}/{product}/token/'
        
        if product == 'disbursement':
            api_user, api_key = self.disb_api_user, self.disb_api_key
            sub_key = self.disb_subscription_key
        else:
            api_user, api_key = self.api_user, self.api_key
            sub_key = self.subscription_key

        if not sub_key:
            raise ProviderError(f'MTN {product} subscription key missing.')

        try:
            resp = requests.post(
                url,
                auth=(api_user, api_key),
                headers={'Ocp-Apim-Subscription-Key': sub_key},
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise ProviderError(f'MTN {product} token request failed: {exc}') from exc

        if resp.status_code >= 400:
            raise ProviderError(f'MTN {product} token error ({resp.status_code}): {resp.text[:300]}')

        token = resp.json().get('access_token')
        self._tokens[product] = token
        return token

    def _auth_headers(self, product='collection', reference_id: str | None = None) -> dict:
        sub_key = self.disb_subscription_key if product == 'disbursement' else self.subscription_key
        headers = {
            'Authorization': f'Bearer {self._get_access_token(product)}',
            'Ocp-Apim-Subscription-Key': sub_key,
            'X-Target-Environment': self.target_environment,
            'Content-Type': 'application/json',
        }
        if reference_id:
            headers['X-Reference-Id'] = reference_id
        if self.config.mtn_callback_url:
            headers['X-Callback-Url'] = self.config.mtn_callback_url
        return headers

    def initiate_payment(self, transaction) -> PaymentResult:
        if not self.config.mtn_enabled:
            raise ProviderError('MTN collections disabled.')
            
        try:
            reference_id = str(uuid.UUID(transaction.reference))
        except ValueError:
            reference_id = str(uuid.uuid4())

        body = {
            'amount': str(transaction.amount),
            'currency': transaction.currency,
            'externalId': transaction.reference,
            'payer': {
                'partyIdType': 'MSISDN',
                'partyId': transaction.phone_number,
            },
            'payerMessage': (transaction.description or 'Payment')[:160],
            'payeeNote': (transaction.description or 'Payment')[:160],
        }

        url = f'{self.base_url}/collection/v1_0/requesttopay'
        try:
            resp = requests.post(
                url, json=body,
                headers=self._auth_headers(product='collection', reference_id=reference_id),
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise ProviderError(f'MTN collection failed: {exc}') from exc

        if resp.status_code >= 400:
            raise ProviderRejectedError(f'MTN collection rejected ({resp.status_code}): {resp.text[:500]}')

        return PaymentResult(
            status=PaymentStatus.PROCESSING,
            provider_transaction_id=reference_id,
            provider_status_code='ACCEPTED',
            provider_status_message='MTN collection accepted.',
            raw_response={'reference_id': reference_id, 'http_status': resp.status_code},
        )

    def initiate_disbursement(self, transaction) -> PaymentResult:
        if not self.config.mtn_disbursement_enabled:
            raise ProviderError('MTN disbursements disabled.')

        try:
            reference_id = str(uuid.UUID(transaction.reference))
        except ValueError:
            reference_id = str(uuid.uuid4())

        body = {
            'amount': str(transaction.amount),
            'currency': transaction.currency,
            'externalId': transaction.reference,
            'payee': {
                'partyIdType': 'MSISDN',
                'partyId': transaction.phone_number,
            },
            'payerMessage': (transaction.description or 'Disbursement')[:160],
            'payeeNote': (transaction.description or 'Disbursement')[:160],
        }

        url = f'{self.base_url}/disbursement/v1_0/transfer'
        try:
            resp = requests.post(
                url, json=body,
                headers=self._auth_headers(product='disbursement', reference_id=reference_id),
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise ProviderError(f'MTN disbursement failed: {exc}') from exc

        if resp.status_code >= 400:
            raise ProviderRejectedError(f'MTN disbursement rejected ({resp.status_code}): {resp.text[:500]}')

        return PaymentResult(
            status=PaymentStatus.PROCESSING,
            provider_transaction_id=reference_id,
            provider_status_code='ACCEPTED',
            provider_status_message='MTN disbursement accepted.',
            raw_response={'reference_id': reference_id, 'http_status': resp.status_code},
        )

    def query_status(self, transaction) -> PaymentResult:
        ref = transaction.provider_transaction_id
        if not ref:
            raise ProviderRejectedError('No provider_transaction_id to query.')

        product = 'disbursement' if transaction.transaction_type == 'disbursement' else 'collection'
        endpoint = 'transfer' if product == 'disbursement' else 'requesttopay'
        
        url = f'{self.base_url}/{product}/v1_0/{endpoint}/{ref}'
        try:
            resp = requests.get(url, headers=self._auth_headers(product=product), timeout=DEFAULT_TIMEOUT)
        except requests.RequestException as exc:
            raise ProviderError(f'MTN query failed: {exc}') from exc

        if resp.status_code >= 400:
            raise ProviderRejectedError(f'MTN query rejected ({resp.status_code}): {resp.text[:300]}')

        data = resp.json()
        mtn_status = (data.get('status') or '').upper()
        canonical = MTN_STATUS_MAP.get(mtn_status, PaymentStatus.PROCESSING)
        return PaymentResult(
            status=canonical,
            provider_transaction_id=ref,
            provider_status_code=mtn_status,
            provider_status_message=data.get('reason', '') or '',
            raw_response=data,
        )

    def parse_callback(self, payload: dict) -> PaymentResult:
        mtn_status = (payload.get('status') or '').upper()
        canonical = MTN_STATUS_MAP.get(mtn_status, PaymentStatus.PROCESSING)
        return PaymentResult(
            status=canonical,
            provider_transaction_id=str(
                payload.get('referenceId') or payload.get('externalId') or ''
            ),
            provider_status_code=mtn_status,
            provider_status_message=payload.get('reason', '') or '',
            raw_response=payload,
        )
