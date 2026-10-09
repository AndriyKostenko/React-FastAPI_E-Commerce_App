"""The real type of an image, read from its first bytes."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SniffedImage:
    content_type: str
    extension: str


class ImageSniffer:
    """
    Recognises JPEG, PNG and WebP by their signatures.

    Neither a client's Content-Type nor a remote server's is trusted: bytes
    that are not one of these three are refused, whatever they claim to be,
    so nothing else is ever published from the catalogue bucket.
    """

    @staticmethod
    def sniff(content: bytes) -> SniffedImage | None:
        if content.startswith(b"\xff\xd8\xff"):
            return SniffedImage("image/jpeg", "jpg")
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return SniffedImage("image/png", "png")
        if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
            return SniffedImage("image/webp", "webp")
        return None
