"""
Avatars (/users/me/avatar) against the real test database and the real object
store: the test catalogue bucket on the local S3 server (SeaweedFS), reached
with user-service's own key, which may touch ``avatars/`` only.
"""
from io import BytesIO

import httpx
import pytest
from fastapi import status
from httpx import AsyncClient
from PIL import Image

from managers import settings as app_settings
from settings import get_test_settings
from tests.conftest import as_gateway
from tests.integration_tests.test_user_routes import _setup_authenticated_user

test_settings = get_test_settings()
API = test_settings.API
AVATAR = f"{API}/users/me/avatar"

pytestmark = pytest.mark.skipif(
    app_settings.OBJECT_STORAGE_BACKEND != "s3" or not app_settings.AWS_S3_CATALOGUE_PUBLIC_BASE_URL,
    reason="needs the S3 test bucket (run through ./local/dev.sh test, or CI)",
)

# EXIF tag 0x8825 is the GPS block a phone camera writes.
GPS_IFD = 0x8825


def _photo_with_location(fmt: str = "JPEG", size: tuple[int, int] = (800, 600)) -> bytes:
    """A camera-like photo: not square, and carrying GPS coordinates in EXIF."""
    image = Image.new("RGB", size, (200, 30, 30))
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"  # Make
    exif[GPS_IFD] = {1: "N", 2: (43.0, 39.0, 0.0), 3: "W", 4: (79.0, 23.0, 0.0)}
    output = BytesIO()
    image.save(output, format=fmt, exif=exif.tobytes())
    return output.getvalue()


async def _token(client: AsyncClient, get_outbox_event) -> str:
    login = await _setup_authenticated_user(client, get_outbox_event)
    return str(login["access_token"])


async def _upload(client: AsyncClient, token: str, content: bytes, name: str = "me.jpg") -> httpx.Response:
    return await client.put(
        AVATAR,
        files={"file": (name, content, "application/octet-stream")},
        headers=as_gateway(token, "PUT", AVATAR),
    )


async def _public(url: str) -> httpx.Response:
    """An anonymous GET, as a browser loading the <img> would make."""
    async with httpx.AsyncClient() as anonymous:
        return await anonymous.get(url)


class TestUpload:
    async def test_upload_stores_a_square_webp_without_metadata(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        token = await _token(integration_client, get_outbox_event)
        response = await _upload(integration_client, token, _photo_with_location())
        assert response.status_code == status.HTTP_200_OK, response.text
        url = response.json()["image"]
        assert url.startswith(f"{app_settings.AWS_S3_CATALOGUE_PUBLIC_BASE_URL.rstrip('/')}/avatars/")

        stored = await _public(url)
        assert stored.status_code == 200
        assert stored.headers["content-type"] == "image/webp"
        with Image.open(BytesIO(stored.content)) as avatar:
            assert avatar.format == "WEBP"
            assert avatar.size == (app_settings.AVATAR_SIZE_PX, app_settings.AVATAR_SIZE_PX)
            # The location (and every other EXIF field) did not survive.
            assert not avatar.getexif()
            assert "exif" not in avatar.info

    async def test_replacing_deletes_the_previous_file(self, integration_client: AsyncClient, get_outbox_event):
        token = await _token(integration_client, get_outbox_event)
        first = (await _upload(integration_client, token, _photo_with_location())).json()["image"]
        second = (await _upload(integration_client, token, _photo_with_location("PNG"), "me.png")).json()["image"]

        assert first != second
        assert (await _public(second)).status_code == 200
        assert (await _public(first)).status_code == 404

    async def test_profile_reads_return_the_url(self, integration_client: AsyncClient, get_outbox_event):
        token = await _token(integration_client, get_outbox_event)
        url = (await _upload(integration_client, token, _photo_with_location())).json()["image"]
        me = (await integration_client.get(f"{API}/me", headers=as_gateway(token, "GET", f"{API}/me"))).json()
        profile_path = f"{API}/users/{me['id']}"
        profile = await integration_client.get(profile_path, headers=as_gateway(token, "GET", profile_path))
        assert profile.json()["image"] == url

    @pytest.mark.parametrize(
        "content,name",
        [
            (b"GIF89a" + b"\x00" * 64, "animated.gif"),
            (b"<svg xmlns='http://www.w3.org/2000/svg'/>", "drawing.svg"),
            (b"\x89PNG\r\n\x1a\n" + b"not really a png", "broken.png"),
            (b"", "empty.jpg"),
        ],
    )
    async def test_non_images_are_refused(self, integration_client: AsyncClient, get_outbox_event, content, name):
        token = await _token(integration_client, get_outbox_event)
        response = await _upload(integration_client, token, content, name)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_oversized_upload_is_refused(self, integration_client: AsyncClient, get_outbox_event):
        token = await _token(integration_client, get_outbox_event)
        too_big = b"\xff\xd8\xff" + b"\x00" * app_settings.AVATAR_MAX_UPLOAD_BYTES
        response = await _upload(integration_client, token, too_big)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    async def test_without_a_session_is_refused(self, integration_client: AsyncClient):
        response = await integration_client.put(AVATAR, files={"file": ("me.jpg", _photo_with_location(), "image/jpeg")})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestRemoval:
    async def test_remove_clears_the_avatar_and_deletes_the_file(
        self, integration_client: AsyncClient, get_outbox_event
    ):
        token = await _token(integration_client, get_outbox_event)
        url = (await _upload(integration_client, token, _photo_with_location())).json()["image"]

        response = await integration_client.delete(AVATAR, headers=as_gateway(token, "DELETE", AVATAR))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["image"] is None
        assert (await _public(url)).status_code == 404

    async def test_deleting_the_account_deletes_the_file(self, integration_client: AsyncClient, get_outbox_event):
        token = await _token(integration_client, get_outbox_event)
        url = (await _upload(integration_client, token, _photo_with_location())).json()["image"]
        me = (await integration_client.get(f"{API}/me", headers=as_gateway(token, "GET", f"{API}/me"))).json()

        path = f"{API}/users/{me['id']}"
        response = await integration_client.delete(path, headers=as_gateway(token, "DELETE", path))
        assert response.status_code == status.HTTP_200_OK
        assert (await _public(url)).status_code == 404
