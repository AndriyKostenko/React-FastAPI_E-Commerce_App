from typing import Any
from urllib.parse import urlencode

from httpx import AsyncClient, HTTPStatusError, RequestError

from exceptions.product_exceptions import CJDropshippingAPIError
from shared.settings import Settings


class CJDropshippingAPIClient:
    """Low-level HTTP client for CJ Dropshipping API 2.0.

    Handles URL construction, authentication headers, token acquisition,
    and generic JSON request/response handling.

    Auth flow:
        1. POST /authentication/getAccessToken with {"apiKey": "..."}
        2. Use the returned accessToken in the CJ-Access-Token header for
           all subsequent requests.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings: Settings = settings
        self._access_token: str | None = None

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

    async def request(self,
				        method: str,
				        url: str,
				        *,
				        json: dict[str, Any] | None = None,
				        params: dict[str, Any] | None = None,
				        access_token: str | None = None) -> dict[str, Any]:
        """Send an HTTP request and return the parsed JSON body."""
        headers = self._auth_headers(access_token)
        try:
            async with AsyncClient() as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json,
                    params=params,
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.json()
        except RequestError as exc:
            raise CJDropshippingAPIError(f"Network error calling CJ API: {exc}") from exc
        except HTTPStatusError as exc:
            raise CJDropshippingAPIError(
                f"CJ API returned {exc.response.status_code}: {exc.response.text}"
            ) from exc

    async def get_access_token(self) -> str:
        """Obtain a CJ access token using the configured API key."""
        response = await self.request(
            "POST",
            self.settings.CJ_DROPSHIPPING_ACCESS_TOKEN_URL,
            json=self.settings.CJ_DROPSHIPPING_AUTH_PAYLOAD,
        )
        access_token = response.get("data", {}).get("accessToken")
        if not access_token:
            raise CJDropshippingAPIError("CJ access token missing in response")
        self._access_token = access_token
        return access_token

    async def ensure_access_token(self) -> str | None:
        """Return a cached token or fetch a new one."""
        if not self._access_token:
            await self.get_access_token()
        return self._access_token
