"""
Provider interface for EFRIS fiscalization.

All providers must return the same shape so the rest of the system never
cares which backend is in use. Swap Mock → Weaf → Direct URA by changing
EfrisConfig.provider — nothing in sales/receipts needs to change.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FiscalResult:
    """Unified response returned by every provider."""
    success: bool
    fdn: str = ''
    invoice_id: str = ''
    verification_code: str = ''
    qr_code: str = ''
    raw_response: dict[str, Any] = field(default_factory=dict)
    error_message: str = ''


class ProviderError(Exception):
    """Raised for retryable errors (network, 5xx, timeouts)."""


class ProviderRejectedError(Exception):
    """Raised when EFRIS definitively rejects the invoice (4xx, validation)."""


class FiscalizationProvider(ABC):
    """Abstract base class for all EFRIS providers."""

    name: str = 'base'

    def __init__(self, config):
        self.config = config  # EfrisConfig instance

    @abstractmethod
    def submit_invoice(self, payload: dict) -> FiscalResult:
        """
        Submit an invoice payload to EFRIS.

        Args:
            payload: dict built by services.build_payload()

        Returns:
            FiscalResult with fdn, invoice_id, verification_code, qr_code

        Raises:
            ProviderError: transient failure (should retry)
            ProviderRejectedError: permanent failure (do not retry)
        """

    def health_check(self) -> bool:
        """Optional health check. Override if the provider supports one."""
        return True
