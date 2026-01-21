from typing import Any, Mapping

from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response
import orjson
from starlette.background import BackgroundTask


class JSONResponse(Response):
    """Custom JSON response class that uses orjson for serialization."""

    media_type = "application/json"

    def __init__(
        self,
        content: Any,
        status_code: int = 200,
        headers: Mapping[str, str] | None = None,
        media_type: str | None = None,
        background: BackgroundTask | None = None,
    ) -> None:
        super().__init__(content, status_code, headers, media_type, background)

    def render(self, content: Any):
        """
        1. Encoding data using jsonable_encoder to ensure all data types are serializable.
        2. Re-assigned rendering the content as JSON using orjson instead of standart json library.
        """
        return orjson.dumps(jsonable_encoder(content))
