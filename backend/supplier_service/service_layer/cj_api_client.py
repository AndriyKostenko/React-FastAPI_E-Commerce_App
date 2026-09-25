from types import TracebackType
from typing import Any, Self
from urllib.parse import urlencode

from logging import Logger, getLogger

from httpx import AsyncClient, HTTPStatusError, RequestError

from shared.resilience import CircuitBreaker, CircuitOpenError, RetryableError, RetryPolicy
from shared.settings import Settings


class CJDropshippingAPIError(Exception):
    """Raised when the CJDropshipping API returns an error or cannot be reached."""
    pass


class CJDropshippingNetworkError(CJDropshippingAPIError, RetryableError):
    """The request outcome is unknown because no authoritative response arrived."""

    pass


class CJDropshippingUnavailableError(CJDropshippingNetworkError):
    """
    CJ gave no authoritative answer: a 5xx, a 429, or our circuit breaker is
    open after repeated failures.

    A subclass of the network error on purpose: every caller already treats
    that as "outcome unknown, try again later" — never as CJ rejecting the
    request, which would fail (and refund) an order because CJ was down.
    """

    pass


# Answers that mean "CJ is not really answering" rather than "CJ said no".
_UNAVAILABLE_STATUSES = frozenset({429, 500, 502, 503, 504})


class CJDropshippingAPIClient:
    """Low-level HTTP client for CJ Dropshipping API 2.0.

    Handles URL construction, authentication headers, token acquisition,
    and generic JSON request/response handling.

    Auth flow:
        1. POST /authentication/getAccessToken with {"apiKey": "..."}
        2. Use the returned accessToken in the CJ-Access-Token header for
           all subsequent requests.
    """

    # One breaker per process, shared by every client instance: API routes,
    # consumers and tasks each build their own client, and a breaker per
    # instance would never see enough failures to trip.
    _shared_breaker: CircuitBreaker | None = None

    def __init__(
        self,
        settings: Settings,
        http_client: AsyncClient | None = None,
        *,
        breaker: CircuitBreaker | None = None,
        retry_policy: RetryPolicy | None = None,
        logger: Logger | None = None,
    ) -> None:
        self.settings: Settings = settings
        self._access_token: str | None = None
        self._http_client = http_client
        self._owns_http_client = http_client is None
        self._logger = logger or getLogger("supplier-service.cj")
        self._breaker = breaker or self._process_breaker(settings, self._logger)
        self._retry_policy = retry_policy or RetryPolicy(
            max_attempts=settings.CJ_DROPSHIPPING_RETRY_MAX_ATTEMPTS
        )

    @classmethod
    def _process_breaker(cls, settings: Settings, logger: Logger) -> CircuitBreaker:
        if cls._shared_breaker is None:
            cls._shared_breaker = CircuitBreaker(
                "cj-dropshipping",
                logger,
                failure_threshold=settings.CJ_DROPSHIPPING_BREAKER_FAILURE_THRESHOLD,
                recovery_timeout=settings.CJ_DROPSHIPPING_BREAKER_RECOVERY_SECONDS,
            )
        return cls._shared_breaker

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
        idempotent: bool | None = None,
        _retry_on_401: bool = True,
    ) -> dict[str, Any]:
        """
        Send an HTTP request and return the parsed JSON body.

        ``idempotent`` (default: GET only) allows retrying a transient failure
        with backoff. It must stay off for writes — create, confirm, pay,
        delete — whose outcome is unknown after a lost response: retrying
        ``pay_balance`` could pay twice. Their callers reconcile instead.
        """
        repeatable = method.upper() == "GET" if idempotent is None else idempotent

        async def attempt() -> dict[str, Any]:
            return await self._send_once(
                method, url, json=json, params=params, access_token=access_token,
                timeout=timeout, _retry_on_401=_retry_on_401,
            )

        if not repeatable:
            return await attempt()
        return await self._retry_policy.run(attempt, name=f"CJ {method} {url}", logger=self._logger)

    async def _send_once(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None,
        params: dict[str, Any] | None,
        access_token: str | None,
        timeout: float | None,
        _retry_on_401: bool,
    ) -> dict[str, Any]:
        """One call through the breaker. A business rejection still proves CJ is up."""
        try:
            self._breaker.before_call()
        except CircuitOpenError as exc:
            raise CJDropshippingUnavailableError(str(exc), retry_after=exc.retry_after) from exc
        try:
            payload = await self._exchange(
                method, url, json=json, params=params, access_token=access_token,
                timeout=timeout, _retry_on_401=_retry_on_401,
            )
        except CJDropshippingNetworkError:
            self._breaker.record_failure()
            raise
        except CJDropshippingAPIError:
            self._breaker.record_success()
            raise
        self._breaker.record_success()
        return payload

    async def _exchange(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None,
        params: dict[str, Any] | None,
        access_token: str | None,
        timeout: float | None,
        _retry_on_401: bool,
    ) -> dict[str, Any]:
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
            payload = response.json()
            if isinstance(payload, dict) and payload.get("result") is False:
                code = payload.get("code", "unknown")
                message = payload.get("message") or "Unknown CJ API error"
                raise CJDropshippingAPIError(
                    f"CJ API request failed ({code}): {message}"
                )
            return payload
        except RequestError as exc:
            raise CJDropshippingNetworkError(f"Network error calling CJ API: {exc}") from exc
        except HTTPStatusError as exc:
            if exc.response.status_code == 401 and _retry_on_401 and url != self.settings.CJ_DROPSHIPPING_ACCESS_TOKEN_URL:
                new_token = await self.ensure_access_token(force_refresh=True)
                return await self._exchange(
                    method,
                    url,
                    json=json,
                    params=params,
                    access_token=new_token,
                    timeout=timeout,
                    _retry_on_401=False,
                )
            if exc.response.status_code in _UNAVAILABLE_STATUSES:
                raise CJDropshippingUnavailableError(
                    f"CJ API returned {exc.response.status_code}: {exc.response.text}",
                    retry_after=_retry_after_seconds(exc.response.headers.get("Retry-After")),
                ) from exc
            raise CJDropshippingAPIError(
                f"CJ API returned {exc.response.status_code}: {exc.response.text}"
            ) from exc

    async def get_access_token(self) -> str:
        """Obtain a CJ access token using the configured API key."""
        response = await self.request(
            "POST",
            self.settings.CJ_DROPSHIPPING_ACCESS_TOKEN_URL,
            json=self.settings.CJ_DROPSHIPPING_AUTH_PAYLOAD,
            idempotent=True,  # issuing a token changes nothing at CJ
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

    async def calculate_freight(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Quote shipping options via freightCalculate.

        Args:
            payload: Request body matching the CJ freightCalculate schema.

        Returns:
            Parsed JSON response from CJ.
        """
        return await self.request(
            "POST",
            self.settings.CJ_DROPSHIPPING_FREIGHT_CALCULATE_URL,
            json=payload,
            timeout=self.settings.CJ_DROPSHIPPING_FREIGHT_TIMEOUT_SECONDS,
            idempotent=True,  # a POST, but only a quote
        )

    async def get_tracking_info(self, tracking_number: str) -> dict[str, Any]:
        """Fetch carrier scan events for one CJ tracking number."""
        return await self.request(
            "GET",
            self.settings.CJ_DROPSHIPPING_TRACK_INFO_URL,
            params={"trackNumber": tracking_number},
        )

    async def get_order_detail(self, order_id: str) -> dict[str, Any]:
        """Query by the merchant order number or CJ order id."""
        return await self.request(
            "GET",
            self.settings.CJ_DROPSHIPPING_ORDER_DETAIL_URL,
            params={"orderId": order_id},
        )

    async def confirm_order(self, cj_order_id: str) -> dict[str, Any]:
        """Confirm a created order, moving it to UNPAID so it can be paid."""
        return await self.request(
            "PATCH",
            self.settings.CJ_DROPSHIPPING_CONFIRM_ORDER_URL,
            json={"orderId": cj_order_id},
        )

    async def get_balance(self) -> dict[str, Any]:
        """Return the account's CJ wallet balance (``data.amount``, USD)."""
        return await self.request("GET", self.settings.CJ_DROPSHIPPING_BALANCE_URL)

    async def pay_balance(self, cj_order_id: str) -> dict[str, Any]:
        """Pay one confirmed order from the CJ wallet balance."""
        return await self.request(
            "POST",
            self.settings.CJ_DROPSHIPPING_PAY_BALANCE_URL,
            json={"orderId": cj_order_id},
        )

    async def delete_order(self, order_id: str) -> dict[str, Any]:
        """Delete a CJ order while it is still in CREATED/IN_CART state."""
        return await self.request(
            "DELETE",
            self.settings.CJ_DROPSHIPPING_DELETE_ORDER_URL,
            params={"orderId": order_id},
        )


def _retry_after_seconds(header: str | None) -> float | None:
    """A Retry-After given in seconds; the HTTP-date form is ignored."""
    try:
        return float(header) if header else None
    except ValueError:
        return None
