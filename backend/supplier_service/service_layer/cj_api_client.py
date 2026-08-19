from types import TracebackType
from typing import Any, Self
from urllib.parse import urlencode

from httpx import AsyncClient, HTTPStatusError, RequestError

from shared.settings import Settings


class CJDropshippingAPIError(Exception):
    """Raised when the CJDropshipping API returns an error or cannot be reached."""
    pass


class CJDropshippingAPIClient:
    """Low-level HTTP client for CJ Dropshipping API 2.0.

    Handles URL construction, authentication headers, token acquisition,
    and generic JSON request/response handling.

    Auth flow:
        1. POST /authentication/getAccessToken with {"apiKey": "..."}
        2. Use the returned accessToken in the CJ-Access-Token header for
           all subsequent requests.
    """

    def __init__(self, settings: Settings, http_client: AsyncClient | None = None) -> None:
        self.settings: Settings = settings
        self._access_token: str | None = None
        self._http_client = http_client
        self._owns_http_client = http_client is None

    async def __aenter__(self) -> Self:
        """Start the owned HTTP client and clean up if startup fails."""
        try:
            await self.start()
        except BaseException:
            await self.close()
            raise
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the owned HTTP client when leaving its async context."""
        await self.close()

    async def start(self) -> None:
        """Create the reusable HTTP client when one was not injected."""
        if self._http_client is None:
            self._http_client = AsyncClient(
                timeout=self.settings.CJ_DROPSHIPPING_REQUEST_TIMEOUT_SECONDS,
            )

    async def close(self) -> None:
        """Close an internally owned reusable HTTP client."""
        if self._http_client is not None and self._owns_http_client:
            await self._http_client.aclose()
            self._http_client = None

    @staticmethod
    def build_url(base_url: str, query_params: dict[str, Any] | None = None) -> str:
        """Append query parameters to a base URL."""
        if not query_params:
            return base_url
        cleaned = {k: v for k, v in query_params.items() if v is not None}
        if not cleaned:
            return base_url
        return f"{base_url}?{urlencode(cleaned, doseq=True)}"

    def _auth_headers(self, access_token: str | None = None) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        token = access_token or self._access_token
        if token:
            headers["CJ-Access-Token"] = token
        return headers

    async def request(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        access_token: str | None = None,
        timeout: float | None = None,
        _retry_on_401: bool = True,
    ) -> dict[str, Any]:
        """Send an HTTP request and return the parsed JSON body."""
        if url != self.settings.CJ_DROPSHIPPING_ACCESS_TOKEN_URL and access_token is None and not self._access_token:
            await self.ensure_access_token()

        headers = self._auth_headers(access_token)
        request_timeout = timeout or self.settings.CJ_DROPSHIPPING_REQUEST_TIMEOUT_SECONDS
        try:
            await self.start()
            assert self._http_client is not None
            response = await self._http_client.request(
                method=method,
                url=url,
                headers=headers,
                json=json,
                params=params,
                timeout=request_timeout,
            )
            response.raise_for_status()
            return response.json()
        except RequestError as exc:
            raise CJDropshippingAPIError(f"Network error calling CJ API: {exc}") from exc
        except HTTPStatusError as exc:
            if exc.response.status_code == 401 and _retry_on_401 and url != self.settings.CJ_DROPSHIPPING_ACCESS_TOKEN_URL:
                new_token = await self.ensure_access_token(force_refresh=True)
                return await self.request(
                    method=method,
                    url=url,
                    json=json,
                    params=params,
                    access_token=new_token,
                    timeout=timeout,
                    _retry_on_401=False,
                )
            raise CJDropshippingAPIError(
                f"CJ API returned {exc.response.status_code}: {exc.response.text}"
            ) from exc

    async def get_access_token(self) -> str:
        """Obtain a CJ access token using the configured API key."""
        response = await self.request(
            "POST",
            self.settings.CJ_DROPSHIPPING_ACCESS_TOKEN_URL,
            json=self.settings.CJ_DROPSHIPPING_AUTH_PAYLOAD,
            _retry_on_401=False,
        )
        access_token = response.get("data", {}).get("accessToken")
        if not access_token:
            raise CJDropshippingAPIError("CJ access token missing in response")
        self._access_token = access_token
        return access_token

    async def ensure_access_token(self, force_refresh: bool = False) -> str | None:
        """Return a cached token or fetch a new one."""
        if not self._access_token or force_refresh:
            await self.get_access_token()
        return self._access_token

    async def create_order_v2(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a CJ Dropshipping order via createOrderV2.

        Args:
            payload: Request body matching the CJ createOrderV2 schema.

        Returns:
            Parsed JSON response from CJ.
        """
        await self.ensure_access_token()
        return await self.request(
            "POST",
            self.settings.CJ_DROPSHIPPING_CREATE_ORDER_URL,
            json=payload,
            access_token=self._access_token,
            timeout=self.settings.CJ_DROPSHIPPING_ORDER_CREATE_TIMEOUT_SECONDS,
        )
