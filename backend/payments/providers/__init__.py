from .base import (
    PaymentProvider, PaymentResult, PaymentStatus,
    ProviderError, ProviderRejectedError,
)
from .mock import MockProvider
from .mtn import MTNProvider
from .airtel import AirtelProvider
from .pesapal import PesapalProvider

__all__ = [
    'PaymentProvider', 'PaymentResult', 'PaymentStatus',
    'ProviderError', 'ProviderRejectedError',
    'MockProvider', 'MTNProvider', 'AirtelProvider', 'PesapalProvider',
    'get_provider_class',
]


def get_provider_class(name: str):
    """Factory: map provider name string to provider class."""
    mapping = {
        'mock': MockProvider,
        'mtn': MTNProvider,
        'airtel': AirtelProvider,
        'pesapal': PesapalProvider,
        # 'flutterwave': pinned — Flutterwave is not currently onboarding SMEs.
    }
    if name not in mapping:
        raise ValueError(
            f'Unknown payment provider: "{name}". '
            f'Available: {list(mapping.keys())}'
        )
    return mapping[name]
