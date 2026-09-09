"""Trustworthy resolution of the originating client address behind proxies."""

from collections.abc import Sequence
from ipaddress import ip_address, ip_network
from typing import Final

from starlette.requests import HTTPConnection


UNKNOWN_CLIENT: Final[str] = "unknown"


class ClientIPResolver:
    """Resolve the originating client address of a proxied request.

    ``X-Forwarded-For`` is attacker-controlled: any client may send one, and
    reverse proxies *append* to it rather than replace it.  Reading the first
    entry therefore hands the caller a value the client chose.  This resolver
    closes that hole two ways:

    * the header is consulted only when the direct peer is a configured proxy,
      so a direct connection is always keyed on its real address;
    * the chain is then walked right to left, because entries a client supplied
      always sit to the left of the addresses real proxies appended.

    An empty ``trusted_proxy_networks`` means no header is ever trusted.
    """

    def __init__(self, trusted_proxy_networks: Sequence[str]) -> None:
        self._trusted_networks = []
        for network in trusted_proxy_networks:
            try:
                self._trusted_networks.append(ip_network(network, strict=False))
            except ValueError:
                # A malformed entry must not silently widen trust.
                continue

    def is_trusted_proxy(self, address: str) -> bool:
        """Report whether an address belongs to a configured proxy network."""
        try:
            parsed = ip_address(address)
        except ValueError:
            return False
        return any(parsed in network for network in self._trusted_networks)

    def resolve(self, connection: HTTPConnection) -> str:
        """Return the client address to attribute this request to."""
        peer = connection.client.host if connection.client else ""
        if not peer:
            return UNKNOWN_CLIENT
        if not self.is_trusted_proxy(peer):
            # Direct connection: every forwarding header is client-controlled.
            return peer

        forwarded_for = connection.headers.get("x-forwarded-for", "")
        for hop in reversed(forwarded_for.split(",")):
            candidate = hop.strip()
            if not candidate or self.is_trusted_proxy(candidate):
                continue
            try:
                ip_address(candidate)
            except ValueError:
                # Garbage in the chain: keep walking towards the client.
                continue
            return candidate
        return peer
