"""Return routes at the gateway: who may call them, photos in, photos out."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest
from httpx import AsyncClient
from httpx import Response as HttpxResponse
from starlette.datastructures import FormData, Headers, UploadFile
from starlette.requests import Request

from gateway.apigateway import ApiGateway, MultipartBody
from resources import logger, settings
from shared.testing.signing_keys import EphemeralSigningKeys
from tests.constants import TEST_API, TEST_ORDER_ID

RETURN_ID = uuid4()
PNG = b"\x89PNG\r\n\x1a\n" + b"\x01" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x02" * 32


def _upload(name: str, content: bytes, content_type: str) -> UploadFile:
    from io import BytesIO

    return UploadFile(BytesIO(content), filename=name, headers=Headers({"content-type": content_type}))


class TestMultipartBody:
    async def test_every_photo_and_the_text_field_survive(self) -> None:
        form = FormData([
            ("request", '{"reason": "defective"}'),
            ("photos", _upload("a.png", PNG, "image/png")),
            ("photos", _upload("b.jpg", JPEG, "image/jpeg")),
        ])

        body = await MultipartBody.from_form(form)

        assert body.data == {"request": ['{"reason": "defective"}']}
        assert body.files == [
            ("photos", ("a.png", PNG, "image/png")),
            ("photos", ("b.jpg", JPEG, "image/jpeg")),
        ]
        assert "\\x89" not in repr(body)  # bytes never reach a log line

    async def test_forwarding_sends_them_as_multipart(self) -> None:
        """Through forward_request, from a real multipart request to the httpx call."""
        encoded = httpx.Request(
            "POST", "http://x", data={"request": "{}"},
            files=[("photos", ("a.png", PNG, "image/png")), ("photos", ("b.jpg", JPEG, "image/jpeg"))],
        )
        raw = encoded.read()
        path = f"/api/v1/orders/{TEST_ORDER_ID}/returns"
        sent_body = [raw]

        async def receive() -> dict[str, object]:
            return {"type": "http.request", "body": sent_body.pop() if sent_body else b"", "more_body": False}

        request = Request({
            "type": "http", "method": "POST", "scheme": "http", "path": path, "raw_path": path.encode(),
            "query_string": b"", "root_path": "", "client": ("203.0.113.9", 1), "server": ("localhost", 8000),
            "headers": [(b"content-type", encoded.headers["content-type"].encode())],
        }, receive)
        request.state.current_user = None
        upstream = MagicMock(spec=HttpxResponse, status_code=201, headers={}, content=b"{}")
        upstream.json.return_value = {}
        client = AsyncMock()
        client.request = AsyncMock(return_value=upstream)
        gateway = ApiGateway(settings=settings, logger=logger, assertion_signer=EphemeralSigningKeys().assertion_signer())

        with patch.object(gateway, "_http_client", client):
            await gateway.forward_request(request=request, service_name="order-service")

        sent = client.request.call_args.kwargs
        assert sent["data"] == {"request": ["{}"]}
        assert [(name, part[0], part[1]) for name, part in sent["files"]] == [
            ("photos", "a.png", PNG), ("photos", "b.jpg", JPEG),
        ]
        # httpx writes its own multipart boundary; ours would not match it.
        assert "content-type" not in {k.lower() for k in sent["headers"]}


class TestReturnRoutes:
    async def test_a_customer_asks_through_the_gateway(self, client: AsyncClient, mock_forward: AsyncMock) -> None:
        response = await client.post(
            f"{TEST_API}/orders/{TEST_ORDER_ID}/returns",
            data={"request": "{}"}, files=[("photos", ("a.png", PNG, "image/png"))],
        )
        assert response.status_code == 200
        mock_forward.assert_awaited_once()

    @pytest.mark.parametrize("action", ["approve", "receive", "reject"])
    async def test_a_customer_cannot_decide(self, client: AsyncClient, mock_forward: AsyncMock, action: str) -> None:
        response = await client.post(f"{TEST_API}/admin/returns/{RETURN_ID}/{action}", json={})
        assert response.status_code == 403
        mock_forward.assert_not_awaited()

    async def test_an_admin_decides(self, admin_client: AsyncClient, mock_forward: AsyncMock) -> None:
        response = await admin_client.post(f"{TEST_API}/admin/returns/{RETURN_ID}/approve", json={})
        assert response.status_code == 200
        mock_forward.assert_awaited_once()

    async def test_an_unknown_decision_is_not_forwarded(self, admin_client: AsyncClient, mock_forward: AsyncMock) -> None:
        response = await admin_client.post(f"{TEST_API}/admin/returns/{RETURN_ID}/refund-twice", json={})
        assert response.status_code == 422
        mock_forward.assert_not_awaited()

    async def test_a_photo_comes_back_as_the_image_itself(
        self, admin_client: AsyncClient, mock_service_request: AsyncMock
    ) -> None:
        mock_service_request.side_effect = None
        mock_service_request.return_value = HttpxResponse(200, content=PNG, headers={"content-type": "image/png"})

        response = await admin_client.get(f"{TEST_API}/admin/returns/{RETURN_ID}/photos/0")

        assert response.status_code == 200
        assert response.content == PNG
        assert response.headers["content-type"] == "image/png"
        assert response.headers["cache-control"] == "private, no-store"

    async def test_a_customer_cannot_see_the_photos(self, client: AsyncClient, mock_service_request: AsyncMock) -> None:
        response = await client.get(f"{TEST_API}/admin/returns/{RETURN_ID}/photos/0")
        assert response.status_code == 403
        mock_service_request.assert_not_awaited()
