import base64

from exceptions.image_generation_exceptions import ImageGenerationProviderError


def decode_image_payload(payload: str, max_bytes: int) -> bytes:
    """
    Decode a provider image payload — a bare base64 string or an
    ``data:image/...;base64,`` URL — into raw bytes, enforcing the size cap
    before and after decoding so an oversized payload is never materialised.
    """
    payload = payload.strip()
    if payload.startswith("data:"):
        header, separator, payload = payload.partition(",")
        if (
            not separator
            or ";base64" not in header.lower()
            or not header.lower().startswith("data:image/")
        ):
            raise ImageGenerationProviderError("Invalid image data URL")

    max_encoded_size = (max_bytes * 4 // 3) + 4
    if not payload or len(payload) > max_encoded_size:
        raise ImageGenerationProviderError("Generated image payload is too large")

    try:
        source_bytes = base64.b64decode(payload, validate=True)
    except ValueError as error:
        raise ImageGenerationProviderError(
            "Generated image payload is not valid base64"
        ) from error

    if not source_bytes or len(source_bytes) > max_bytes:
        raise ImageGenerationProviderError("Generated image payload is too large")
    return source_bytes


def encode_png_data_url(png_bytes: bytes) -> str:
    """Wrap PNG bytes in the same data-URL shape the provider returns."""
    return f"data:image/png;base64,{base64.b64encode(png_bytes).decode('ascii')}"
