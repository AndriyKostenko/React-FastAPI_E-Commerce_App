"""Downloads a supplier image so it can be copied into the catalogue store."""

from dataclasses import dataclass
from urllib.parse import urlsplit

from aiohttp import ClientError, ClientSession, ClientTimeout

from storage.image_sniffer import ImageSniffer, SniffedImage


class CatalogueImageFetchError(Exception):
    """The image could not be fetched, or what came back is not acceptable."""

    def __init__(self, message: str, permanent: bool = False) -> None:
        super().__init__(message)
        # Permanent: retrying can never succeed (a host we never fetch from).
        self.permanent = permanent


@dataclass(frozen=True, slots=True)
class ImageSourcePolicy:
    """Where catalogue images may be downloaded from."""

    schemes: tuple[str, ...]
    # ".example.com" matches every subdomain of example.com.
    domain_suffixes: tuple[str, ...] = ()
    hosts: tuple[str, ...] = ()

    def allows(self, url: str) -> bool:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if parts.scheme not in self.schemes or not host:
            return False
        return host in self.hosts or host.endswith(self.domain_suffixes)


# CJ serves product images from subdomains of cjdropshipping.com
# (cf.cjdropshipping.com, oss-cf.cjdropshipping.com), over HTTPS.
CJ_IMAGE_SOURCES = ImageSourcePolicy(schemes=("https",), domain_suffixes=(".cjdropshipping.com",))


@dataclass(frozen=True, slots=True)
class FetchedImage:
    content: bytes
    image: SniffedImage


class CatalogueImageFetcher:
    """
    GETs one image from a supplier CDN.

    Only URLs the source policy allows are fetched (by default HTTPS on CJ's
    own CDN domains), and redirects are not followed: a URL in the catalogue
    must never make this service request an arbitrary or internal address
    (SSRF). The body is capped while it streams and its type is read from
    its bytes.
    """

    _CHUNK_BYTES = 64 * 1024

    def __init__(
        self,
        session: ClientSession,
        max_bytes: int,
        timeout_seconds: float = 20.0,
        sources: ImageSourcePolicy = CJ_IMAGE_SOURCES,
    ) -> None:
        self._session = session
        self._max_bytes = max_bytes
        self._timeout = ClientTimeout(total=timeout_seconds)
        self._sources = sources

    async def fetch(self, url: str) -> FetchedImage:
        if not self._sources.allows(url):
            raise CatalogueImageFetchError(f"Not a supplier CDN URL: {url}", permanent=True)
        try:
            async with self._session.get(url, timeout=self._timeout, allow_redirects=False) as response:
                if response.status != 200:
                    raise CatalogueImageFetchError(f"HTTP {response.status} from {url}")
                if response.content_length is not None and response.content_length > self._max_bytes:
                    raise CatalogueImageFetchError(
                        f"{url} is {response.content_length} bytes, over {self._max_bytes}", permanent=True
                    )
                body = bytearray()
                async for chunk in response.content.iter_chunked(self._CHUNK_BYTES):
                    body.extend(chunk)
                    # Checked while streaming: a missing or false
                    # Content-Length cannot make us hold an unbounded body.
                    if len(body) > self._max_bytes:
                        raise CatalogueImageFetchError(f"{url} is over {self._max_bytes} bytes", permanent=True)
        except (ClientError, TimeoutError) as error:
            raise CatalogueImageFetchError(f"Could not fetch {url}: {error!r}") from error

        content = bytes(body)
        sniffed = ImageSniffer.sniff(content)
        if sniffed is None:
            # Retried: a CDN answering 200 with an error page is usually passing.
            raise CatalogueImageFetchError(f"{url} is not a JPEG, PNG or WebP image")
        return FetchedImage(content=content, image=sniffed)
