"""
Weaf Company Uganda EFRIS provider.

Stub implementation — requires real Weaf API credentials and endpoint docs.
Fills in the HTTP plumbing so the moment we have:

    - A sandbox base URL
    - An API key or OAuth credentials
    - The real request/response schema

...only the payload mapping and response parsing need to be fleshed out.

Contact Weaf for integration:
    phone:  +256 756 508361
    email:  services@weafcompany.com
    docs:   https://weafmall.com/blog/weaf-efris-api-documentation-...
"""
import logging
import requests
from .base import (
    FiscalizationProvider, FiscalResult, ProviderError, ProviderRejectedError,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 20  # seconds


class WeafProvider(FiscalizationProvider):
    name = 'weaf'

    def __init__(self, config):
        super().__init__(config)
        if not config.weaf_api_key:
            raise ProviderError(
                'Weaf provider selected but weaf_api_key is not configured. '
                'Set EfrisConfig.weaf_api_key or switch provider to "mock".'
            )
        if not config.weaf_base_url:
            raise ProviderError(
                'Weaf provider selected but weaf_base_url is not configured.'
            )
        self.base_url = config.weaf_base_url.rstrip('/')
        self.api_key = config.weaf_api_key

    def _headers(self):
        return {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    def submit_invoice(self, payload: dict) -> FiscalResult:
        """
        POST the invoice to Weaf's EFRIS API.

        NOTE: The exact endpoint path and payload/response structure depend on
        Weaf's published API contract, which requires signup. Update the
        ``endpoint`` and response parsing below once you have the real docs.
        """
        endpoint = f'{self.base_url}/api/efris/invoices'

        try:
            response = requests.post(
                endpoint,
                json=payload,
                headers=self._headers(),
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.Timeout as exc:
            raise ProviderError(f'Weaf timeout: {exc}') from exc
        except requests.ConnectionError as exc:
            raise ProviderError(f'Weaf connection error: {exc}') from exc

        # 4xx = permanent rejection (bad payload, invalid TIN, etc.)
        if 400 <= response.status_code < 500:
            raise ProviderRejectedError(
                f'Weaf rejected invoice ({response.status_code}): {response.text[:500]}'
            )

        # 5xx = retryable
        if response.status_code >= 500:
            raise ProviderError(
                f'Weaf server error ({response.status_code}): {response.text[:500]}'
            )

        data = response.json()

        # TODO: Update field mapping once Weaf API schema is confirmed.
        return FiscalResult(
            success=True,
            fdn=str(data.get('fdn', '')),
            invoice_id=str(data.get('invoiceId', '')),
            verification_code=str(data.get('verificationCode', '')),
            qr_code=str(data.get('qrCode', '')),
            raw_response=data,
        )

    def health_check(self) -> bool:
        try:
            response = requests.get(
                f'{self.base_url}/api/health',
                headers=self._headers(),
                timeout=5,
            )
            return response.ok
        except requests.RequestException:
            return False
