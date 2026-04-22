"""
Shared validators used across apps.

`validate_provider_url` is applied to admin-editable URL fields (payment
provider base URLs, EFRIS provider URLs) to prevent SSRF: a tenant admin
account compromised by an attacker could otherwise point our outbound
HTTP calls at internal metadata services or RFC1918 hosts and exfiltrate
credentials/secrets.
"""
import ipaddress
import socket
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ValidationError


_ALLOWED_SCHEMES = {'http', 'https'}


def _resolve_all(host: str):
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        # Unresolvable at validation time — let the runtime call fail noisily
        # rather than block legitimate hostnames behind split-horizon DNS.
        return []
    return [ipaddress.ip_address(info[4][0]) for info in infos]


def validate_provider_url(value: str) -> None:
    """Reject internal/loopback targets and (in production) plain http://."""
    if not value:
        return

    parsed = urlparse(value)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValidationError('Provider URL must use http or https.')

    if not settings.DEBUG and parsed.scheme != 'https':
        raise ValidationError('Provider URL must use https in production.')

    host = parsed.hostname
    if not host:
        raise ValidationError('Provider URL must include a hostname.')

    # Block obviously dangerous literal targets fast.
    forbidden_hosts = {'localhost', 'metadata.google.internal'}
    if host.lower() in forbidden_hosts:
        raise ValidationError(f'"{host}" is not allowed as a provider URL host.')

    # Resolve DNS and reject if any A/AAAA record points to a private,
    # loopback, link-local, or reserved range.
    for ip in _resolve_all(host):
        if (
            ip.is_private or ip.is_loopback or ip.is_link_local
            or ip.is_reserved or ip.is_multicast or ip.is_unspecified
        ):
            raise ValidationError(
                f'Provider URL resolves to a disallowed address ({ip}).'
            )
