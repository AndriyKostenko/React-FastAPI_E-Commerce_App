"""
Catalogue image references -> URLs a browser can load.

The database stores an object *key* for every image held in the catalogue
store (``catalogue/cj/...``, ``catalogue/uploads/...``); the public origin is
added only on the way out, so moving the bucket behind a CDN is a settings
change, not a data migration. A value that is already a URL is passed through
untouched: a CJ image not yet copied keeps being served from CJ.
"""

from functools import lru_cache
from typing import Annotated
from urllib.parse import quote

from pydantic import AfterValidator
from shared.settings import Settings, get_settings

from storage.object_store import ObjectStorageNotConfiguredError


class CatalogueUrlResolver:
    # http(s) URLs (CJ, not yet copied) and root-relative paths (old /media
    # values) are already loadable as they are.
    _PASSTHROUGH_PREFIXES = ("http://", "https://", "/")

    def __init__(self, public_base_url: str) -> None:
        self._base = public_base_url.rstrip("/")

    @classmethod
    def from_settings(cls, settings: Settings) -> "CatalogueUrlResolver":
        if settings.OBJECT_STORAGE_BACKEND == "local":
            return cls("/media")
        if not settings.AWS_S3_CATALOGUE_PUBLIC_BASE_URL:
            raise ObjectStorageNotConfiguredError(
                "AWS_S3_CATALOGUE_PUBLIC_BASE_URL is required when OBJECT_STORAGE_BACKEND=s3"
            )
        return cls(settings.AWS_S3_CATALOGUE_PUBLIC_BASE_URL)

    def resolve(self, value: str) -> str:
        if not value or value.startswith(self._PASSTHROUGH_PREFIXES):
            return value
        return f"{self._base}/{quote(value, safe='/')}"


@lru_cache
def _process_resolver() -> CatalogueUrlResolver:
    return CatalogueUrlResolver.from_settings(get_settings())


def resolve_catalogue_url(value: str) -> str:
    return _process_resolver().resolve(value)


# For response schemas only. An input schema must keep the key as it is, or
# the absolute URL would be written back to the database.
CatalogueImageUrl = Annotated[str, AfterValidator(resolve_catalogue_url)]
