"""§29.2 network policy: http/https only, no private or internal destinations."""

from __future__ import annotations

import ipaddress
import os
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from searcher.core.errors import SsrfBlocked

ALLOWED_SCHEMES = frozenset({"http", "https"})
BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "ip6-localhost",
        "ip6-loopback",
        "metadata.google.internal",
        "metadata.goog",
        "metadata",
        "internal",
        "intranet",
        "corp",
        "lan",
    }
)
BLOCKED_HOST_SUFFIXES = (".internal", ".local", ".localhost", ".corp", ".lan", ".home")


@dataclass(frozen=True, slots=True)
class UrlSafety:
    url: str
    host: str
    scheme: str
    resolved: tuple[str, ...]


def _host_blocked_by_name(host: str) -> bool:
    lowered = host.strip(".").lower()
    if lowered in BLOCKED_HOSTNAMES:
        return True
    return any(lowered.endswith(suffix) for suffix in BLOCKED_HOST_SUFFIXES)


def _ip_is_blocked(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return True
    if loopback_allowed() and ip.is_loopback:
        return False
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or (ip.version == 4 and ip in ipaddress.ip_network("100.64.0.0/10"))
        or (ip.version == 6 and ip in ipaddress.ip_network("fc00::/7"))
        or (ip.version == 4 and ip in ipaddress.ip_network("0.0.0.0/8"))
    )


def _literal_ip(host: str) -> str | None:
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        return None


def resolve_host(host: str) -> tuple[str, ...]:
    literal = _literal_ip(host)
    if literal is not None:
        return (literal,)
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise SsrfBlocked(f"DNS resolution failed for {host}", url=host) from exc
    addresses: list[str] = []
    for info in infos:
        sockaddr = info[4]
        if sockaddr:
            addresses.append(str(sockaddr[0]))
    if not addresses:
        raise SsrfBlocked(f"no addresses resolved for {host}", url=host)
    return tuple(dict.fromkeys(addresses))


def loopback_allowed() -> bool:
    """Test-only escape hatch. Production never sets this."""
    return os.environ.get("SEARCHER_ALLOW_LOOPBACK") == "1"


def assert_url_safe(url: str, *, resolve: bool = True) -> UrlSafety:
    """Refuse schemes, hosts, and (optionally) resolved IPs that §29.2 blocks."""
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        raise SsrfBlocked(f"scheme {scheme!r} is not allowed", url=url)
    if parsed.username or parsed.password:
        raise SsrfBlocked("userinfo in URL is not allowed", url=url)
    host = (parsed.hostname or "").strip().lower()
    if not host:
        raise SsrfBlocked("URL has no host", url=url)
    loopback_names = {"localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback"}
    if _host_blocked_by_name(host) and not (loopback_allowed() and host in loopback_names):
        raise SsrfBlocked(f"hostname {host} is blocked", url=url)
    literal = _literal_ip(host)
    resolved: tuple[str, ...]
    if literal is not None:
        if _ip_is_blocked(literal):
            raise SsrfBlocked(f"literal address {literal} is blocked", url=url)
        resolved = (literal,)
    elif resolve:
        resolved = resolve_host(host)
        for address in resolved:
            if _ip_is_blocked(address):
                raise SsrfBlocked(
                    f"resolved address {address} of {host} is blocked",
                    url=url,
                )
    else:
        resolved = ()
    return UrlSafety(url=url, host=host, scheme=scheme, resolved=resolved)


def join_redirect(current: str, location: str) -> str:
    if not location:
        raise SsrfBlocked("empty redirect location", url=current)
    return urljoin(current, location)


def assert_redirect_safe(current: str, location: str) -> str:
    """Re-validate every hop. A private hop after a public start is refused."""
    nxt = join_redirect(current, location)
    assert_url_safe(nxt, resolve=True)
    return nxt
