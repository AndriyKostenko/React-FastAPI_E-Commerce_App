"""The avatar URL type for response schemas (see AvatarUrlResolver)."""

from functools import lru_cache
from typing import Annotated

from pydantic import AfterValidator

from settings import get_settings
from storage.avatar_storage import AvatarUrlResolver


@lru_cache
def _process_resolver() -> AvatarUrlResolver:
    return AvatarUrlResolver(get_settings().AWS_S3_CATALOGUE_PUBLIC_BASE_URL)


def _resolve(value: str | None) -> str | None:
    return _process_resolver().resolve(value)


# For response schemas only: an input schema must keep the key, or the URL
# would be written back to the database.
AvatarUrl = Annotated[str | None, AfterValidator(_resolve)]
