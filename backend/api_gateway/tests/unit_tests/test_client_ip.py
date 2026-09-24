"""Tests for ClientIPResolver — the spoofing boundary for every rate limit."""

from starlette.requests import HTTPConnection

from shared.utils.client_ip import UNKNOWN_CLIENT, ClientIPResolver


TRUSTED = ["172.16.0.0/12", "10.0.0.0/8"]


def _connection(headers: dict[str, str] | None = None, peer: str | None = "203.0.113.9") -> HTTPConnection:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [
            (key.lower().encode(), value.encode())
            for key, value in (headers or {}).items()
        ],
    }
    if peer is not None:
        scope["client"] = (peer, 51234)
    return HTTPConnection(scope)


class TestUntrustedPeer:
    """A direct caller may say anything; none of it may be believed."""

    def setup_method(self):
        self.resolver = ClientIPResolver(TRUSTED)

    def test_uses_peer_address(self):
        assert self.resolver.resolve(_connection()) == "203.0.113.9"

    def test_ignores_forwarded_for(self):
        connection = _connection({"x-forwarded-for": "1.2.3.4"})
        assert self.resolver.resolve(connection) == "203.0.113.9"

    def test_ignores_real_ip(self):
        connection = _connection({"x-real-ip": "1.2.3.4"})
        assert self.resolver.resolve(connection) == "203.0.113.9"

    def test_missing_client_is_unknown(self):
        assert self.resolver.resolve(_connection(peer=None)) == UNKNOWN_CLIENT


class TestTrustedProxy:
    """Behind a proxy the header is read, but only from the right."""

    def setup_method(self):
        self.resolver = ClientIPResolver(TRUSTED)

    def test_single_hop_returns_client(self):
        connection = _connection({"x-forwarded-for": "198.51.100.7"}, peer="172.20.0.4")
        assert self.resolver.resolve(connection) == "198.51.100.7"

    def test_client_prepended_entries_lose_to_the_appended_one(self):
        # Traefik appends the real peer, so anything the client invented sits
        # to its left and must never be selected.
        connection = _connection(
            {"x-forwarded-for": "1.2.3.4, 5.6.7.8, 198.51.100.7"},
            peer="172.20.0.4",
        )
        assert self.resolver.resolve(connection) == "198.51.100.7"

    def test_spoofed_private_address_does_not_shift_the_walk(self):
        connection = _connection(
            {"x-forwarded-for": "10.9.9.9, 198.51.100.7"},
            peer="172.20.0.4",
        )
        assert self.resolver.resolve(connection) == "198.51.100.7"

    def test_trailing_proxy_hops_are_skipped(self):
        connection = _connection(
            {"x-forwarded-for": "198.51.100.7, 10.1.1.1"},
            peer="172.20.0.4",
        )
        assert self.resolver.resolve(connection) == "198.51.100.7"

    def test_garbage_entries_are_skipped(self):
        connection = _connection(
            {"x-forwarded-for": "198.51.100.7, not-an-ip"},
            peer="172.20.0.4",
        )
        assert self.resolver.resolve(connection) == "198.51.100.7"

    def test_all_hops_trusted_falls_back_to_peer(self):
        connection = _connection({"x-forwarded-for": "10.1.1.1"}, peer="172.20.0.4")
        assert self.resolver.resolve(connection) == "172.20.0.4"

    def test_no_header_falls_back_to_peer(self):
        assert self.resolver.resolve(_connection(peer="172.20.0.4")) == "172.20.0.4"


class TestTrustConfiguration:
    def test_empty_trust_list_never_reads_headers(self):
        resolver = ClientIPResolver([])
        connection = _connection({"x-forwarded-for": "1.2.3.4"}, peer="172.20.0.4")
        assert resolver.resolve(connection) == "172.20.0.4"

    def test_malformed_network_entry_does_not_widen_trust(self):
        resolver = ClientIPResolver(["not-a-network", "172.16.0.0/12"])
        assert resolver.is_trusted_proxy("172.20.0.4") is True
        assert resolver.is_trusted_proxy("203.0.113.9") is False
