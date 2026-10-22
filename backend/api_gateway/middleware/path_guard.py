import re
from logging import Logger

from fastapi import Request, Response
from fastapi.responses import JSONResponse


class RequestPathGuard:
    """
    Refuses a request path the proxy could forward somewhere other than where
    it was routed, before authentication, the cache or any route sees it.

    The gateway decides who may call a route from the path it matched, then
    forwards that same path to a service. Two things can make the forwarded
    path differ from the matched one:

    - dot segments: httpx resolves "." and ".." while building the upstream
      URL (RFC 3986), so "/api/v1/products/../orders" is judged as a public
      catalogue path here and sent on as "/api/v1/orders". The /media proxy,
      which signs no caller assertion, reached any product-service path so;
    - characters uvicorn has already percent-decoded: a "%3F" or "%23" in the
      path becomes a "?" or "#" that splits the forwarded URL, and a "%25"
      becomes a "%" the service decodes a second time.

    The path is decoded once (by uvicorn) when this runs, so "%2e%2e" and
    "%2f" arrive as the segments and slashes they spell. No route of ours
    takes anything but letters, digits, "-", "_", "." and "~" in a segment
    (ids, slugs, object keys), so nothing legitimate is refused.
    """

    _ALLOWED_PATH = re.compile(r"[A-Za-z0-9._~/-]*")
    _DOT_SEGMENTS = frozenset({".", ".."})

    def __init__(self, logger: Logger) -> None:
        self._logger = logger

    @classmethod
    def is_safe(cls, path: str) -> bool:
        if cls._ALLOWED_PATH.fullmatch(path) is None:
            return False
        return not any(segment in cls._DOT_SEGMENTS for segment in path.split("/"))

    async def __call__(self, request: Request, call_next) -> Response:
        # The scope's decoded path, not request.url.path: Starlette builds
        # request.url by parsing that path again, so a decoded "?" or "#" has
        # already been split off there and would never be seen.
        path = request.scope["path"]
        if self.is_safe(path):
            return await call_next(request)
        # repr(): the path is the caller's, so it is logged quoted and escaped.
        self._logger.warning("Refused request path %r", path)
        return JSONResponse(status_code=400, content={"detail": "Invalid request path"})
