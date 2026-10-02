"""Every link an email carries, built in one place so each opens a real page."""

from urllib.parse import quote
from uuid import UUID


class EmailLinks:
    """
    Builds the frontend URLs that go into emails.

    Every link starts at FRONTEND_URL: emails used to mix that with
    APP_HOST (no port, so the wrong origin locally) and even the gateway's
    API, whose POST-only /login cannot be opened in a browser.

    One-time tokens travel in the URL fragment (``#token=``). A browser never
    sends the fragment to a server, so the token stays out of access logs,
    proxies and Referer headers; the page reads it from ``location.hash``.
    """

    def __init__(self, frontend_url: str) -> None:
        self._base = frontend_url.rstrip("/")

    def activation(self, token: str) -> str:
        return f"{self._base}/activate#token={quote(token, safe='')}"

    def password_reset(self, token: str) -> str:
        return f"{self._base}/password-reset#token={quote(token, safe='')}"

    def login(self) -> str:
        return f"{self._base}/login"

    def order(self, order_id: UUID | str) -> str:
        return f"{self._base}/order/{order_id}"

    @staticmethod
    def support(contact_email: str) -> str:
        """There is no support page yet: support is a reply to the shop's mailbox."""
        return f"mailto:{contact_email}"
