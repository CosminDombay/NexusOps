"""Client-IP resolution and rate-limit bucketing.

X-Forwarded-For is attacker-controlled. nginx's $proxy_add_x_forwarded_for
appends the real peer to whatever the caller sent, so reading the leftmost
entry let a caller mint a fresh rate-limit bucket per request and forge the
source IP recorded on audit events.
"""

import pytest

from backend.app.core.client_ip import client_ip, client_ip_or_unknown
from backend.app.core.security import InMemoryRateLimitMiddleware
from backend.app.modules.audit.service import source_ip_from_request


class _Client:
    def __init__(self, host: str | None) -> None:
        self.host = host


class _Request:
    def __init__(self, peer: str | None = "10.0.0.9", forwarded_for: str | None = None) -> None:
        self.client = _Client(peer) if peer else None
        self.headers = {"x-forwarded-for": forwarded_for} if forwarded_for else {}


def test_header_is_ignored_without_configured_proxies() -> None:
    request = _Request(peer="10.0.0.9", forwarded_for="1.2.3.4")
    assert client_ip(request, trusted_proxy_hops=0) == "10.0.0.9"


def test_spoofed_prefix_cannot_override_real_peer() -> None:
    """The shape nginx produces: <spoofed>, <real peer>."""
    request = _Request(peer="172.18.0.5", forwarded_for="1.2.3.4, 203.0.113.7")
    assert client_ip(request, trusted_proxy_hops=1) == "203.0.113.7"


def test_single_proxy_reads_appended_peer() -> None:
    request = _Request(peer="172.18.0.5", forwarded_for="203.0.113.7")
    assert client_ip(request, trusted_proxy_hops=1) == "203.0.113.7"


def test_two_proxies_skip_both_appended_hops() -> None:
    request = _Request(peer="172.18.0.5", forwarded_for="1.2.3.4, 203.0.113.7, 172.18.0.2")
    assert client_ip(request, trusted_proxy_hops=2) == "203.0.113.7"


def test_short_chain_falls_back_to_leftmost_not_forgery() -> None:
    """A chain shorter than the hop count means the request skipped a proxy."""
    request = _Request(peer="172.18.0.5", forwarded_for="203.0.113.7")
    assert client_ip(request, trusted_proxy_hops=3) == "203.0.113.7"


def test_missing_header_uses_peer_even_behind_proxy() -> None:
    request = _Request(peer="172.18.0.5")
    assert client_ip(request, trusted_proxy_hops=1) == "172.18.0.5"


def test_no_request_returns_none() -> None:
    assert client_ip(None) is None
    assert source_ip_from_request(None) is None


def test_missing_peer_returns_none_but_never_breaks_bucketing() -> None:
    assert client_ip(_Request(peer=None)) is None
    assert client_ip_or_unknown(_Request(peer=None)) == "unknown"


def test_whitespace_entries_are_tolerated() -> None:
    request = _Request(peer="172.18.0.5", forwarded_for="  1.2.3.4 ,  203.0.113.7  ")
    assert client_ip(request, trusted_proxy_hops=1) == "203.0.113.7"


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/api/v1/auth/login", "/api/v1/auth/login"),
        ("/api/v1/servers/11111111-1111-1111-1111-111111111111", "/api/v1/servers/:id"),
        ("/api/v1/servers/11111111-1111-1111-1111-111111111111/jobs", "/api/v1/servers/:id/jobs"),
        ("/api/v1/proxmox/vms/node1/qemu/101/status", "/api/v1/proxmox/vms/node1/qemu/:id/status"),
    ],
)
def test_identifier_segments_collapse_into_one_bucket(path: str, expected: str) -> None:
    assert InMemoryRateLimitMiddleware._bucket_path(path) == expected


def test_bucket_map_is_bounded() -> None:
    """Varying the path must not grow the hit map without bound."""
    middleware = InMemoryRateLimitMiddleware.__new__(InMemoryRateLimitMiddleware)
    from collections import OrderedDict

    middleware._hits = OrderedDict()
    middleware._max_tracked_keys = 16

    for index in range(500):
        middleware._touch(f"1.2.3.4:GET:/path-{index}", now=1000.0)

    assert len(middleware._hits) <= 16


def test_expired_entries_are_dropped_from_the_window() -> None:
    middleware = InMemoryRateLimitMiddleware.__new__(InMemoryRateLimitMiddleware)
    from collections import OrderedDict

    middleware._hits = OrderedDict()
    middleware._max_tracked_keys = 100

    hits = middleware._touch("k", now=0.0)
    hits.append(0.0)
    assert len(middleware._touch("k", now=30.0)) == 1
    # Past the 60s window the recorded hit ages out.
    assert len(middleware._touch("k", now=120.0)) == 0
