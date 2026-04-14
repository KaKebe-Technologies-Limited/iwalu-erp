from .base import (
    FiscalizationProvider, FiscalResult, ProviderError, ProviderRejectedError,
)
from .mock import MockProvider
from .weaf import WeafProvider

__all__ = [
    'FiscalizationProvider', 'FiscalResult', 'ProviderError',
    'ProviderRejectedError', 'MockProvider', 'WeafProvider',
    'get_provider_class',
]


def get_provider_class(name: str):
    """Factory: map provider name string to provider class."""
    mapping = {
        'mock': MockProvider,
        'weaf': WeafProvider,
    }
    if name not in mapping:
        raise ValueError(
            f'Unknown fiscalization provider: "{name}". '
            f'Available: {list(mapping.keys())}'
        )
    return mapping[name]
