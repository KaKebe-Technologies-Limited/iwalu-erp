"""
Provider interface for mobile money & card payments.

All providers return the same shape so the rest of the system never cares
which backend is in use. Add a new provider by subclassing PaymentProvider
and registering it in providers/__init__.py.

Unlike fiscalization (which is fire-and-forget), payments are inherently
asynchronous: we initiate, then poll or wait for a callback. The provider
interface therefore exposes both `initiate_payment` and `query_status`,
plus a `parse_callback` hook for webhook handlers.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PaymentStatus(str, Enum):
    """Canonical status values, mapped to by every provider."""
    PENDING = 'pending'
    PROCESSING = 'processing'
    SUCCESS = 'success'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    EXPIRED = 'expired'


@dataclass
class PaymentResult:
    """Unified response returned by every provider call."""
    status: PaymentStatus
    provider_transaction_id: str = ''
    provider_status_code: str = ''
    provider_status_message: str = ''
    raw_response: dict[str, Any] = field(default_factory=dict)
    error_message: str = ''

    @property
    def is_success(self) -> bool:
        return self.status == PaymentStatus.SUCCESS

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            PaymentStatus.SUCCESS, PaymentStatus.FAILED,
            PaymentStatus.CANCELLED, PaymentStatus.EXPIRED,
        )


class ProviderError(Exception):
    """Raised for retryable errors (network, 5xx, timeouts)."""


class ProviderRejectedError(Exception):
    """Raised when the provider definitively rejects the request (4xx, validation)."""


class PaymentProvider(ABC):
    """
    Abstract base class for all payment providers.

    Subclasses must declare:
        name             — short identifier matching PaymentConfig.PROVIDER_CHOICES
        supported_methods — tuple of method strings ('mobile_money', 'card', 'bank')
    """
    name: str = 'base'
    supported_methods: tuple = ()

    def __init__(self, config):
        self.config = config  # PaymentConfig instance

    @abstractmethod
    def initiate_payment(self, transaction) -> PaymentResult:
        """
        Initiate a collection (request money from customer).
        """

    @abstractmethod
    def initiate_disbursement(self, transaction) -> PaymentResult:
        """
        Initiate a disbursement (send money to customer/staff/supplier).
        """

    @abstractmethod
    def query_status(self, transaction) -> PaymentResult:
        """
        Query the current status of an in-flight transaction.

        Used both by polling jobs and by the manual "check status" endpoint.
        """

    def parse_callback(self, payload: dict) -> PaymentResult:
        """
        Parse a webhook/callback payload from the provider.

        Default implementation raises NotImplementedError. Override in any
        provider that supports server-to-server callbacks (most do).
        """
        raise NotImplementedError(
            f'Provider {self.name} does not implement parse_callback().'
        )

    def health_check(self) -> bool:
        """Optional health check. Override if the provider supports one."""
        return True
