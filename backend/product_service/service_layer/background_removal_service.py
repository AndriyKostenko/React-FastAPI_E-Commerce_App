import io
from abc import ABC, abstractmethod
from asyncio import to_thread
from logging import Logger
from threading import Lock
from typing import ClassVar, override

from PIL import Image, UnidentifiedImageError
from rembg import new_session, remove
from rembg.sessions.base import BaseSession

from exceptions.image_generation_exceptions import ImageBackgroundRemovalError
from service_layer.image_payload import decode_image_payload, encode_png_data_url
from shared.settings import Settings


class BackgroundRemover(ABC):
    """Turns a generated design into a cutout on a transparent background."""

    @abstractmethod
    async def remove(self, image_payload: str) -> str:
        """
        Take a provider payload (base64 or data URL) and return a PNG data URL
        of the same size with the background made transparent.

        Raises:
            ImageBackgroundRemovalError: the cutout failed or would not print.
        """
        ...


class RembgBackgroundRemover(BackgroundRemover):
    """
    Local ONNX background removal via rembg.

    Loading a model takes seconds (and downloads it on first use), so sessions
    are cached per model name for the life of the process and shared by every
    job the worker runs. Inference is CPU-bound, so it runs in a thread to
    keep the event loop — and the worker's other jobs — responsive.
    """

    _sessions: ClassVar[dict[str, BaseSession]] = {}
    _sessions_lock: ClassVar[Lock] = Lock()

    def __init__(self, settings: Settings, logger: Logger) -> None:
        self._settings = settings
        self._logger = logger
        self._model_name = settings.PRODUCT_IMAGE_BG_REMOVAL_MODEL
        self._min_foreground_ratio = settings.PRODUCT_IMAGE_BG_MIN_FOREGROUND_RATIO

    @override
    async def remove(self, image_payload: str) -> str:
        source_bytes = decode_image_payload(image_payload, self._settings.PRINT_IMAGE_MAX_BYTES)
        png_bytes = await to_thread(self._remove_sync, source_bytes)
        return encode_png_data_url(png_bytes)

    def _session(self) -> BaseSession:
        # Double-checked so concurrent first jobs load the model only once.
        session = self._sessions.get(self._model_name)
        if session is None:
            with self._sessions_lock:
                session = self._sessions.get(self._model_name)
                if session is None:
                    self._logger.info("Loading background-removal model %s", self._model_name)
                    session = new_session(self._model_name)
                    self._sessions[self._model_name] = session
        return session

    def _remove_sync(self, source_bytes: bytes) -> bytes:
        try:
            with Image.open(io.BytesIO(source_bytes)) as source:
                source.load()
                icc_profile = source.info.get("icc_profile")
                rgba = source.convert("RGBA")
        except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as error:
            raise ImageBackgroundRemovalError("Generated image could not be read") from error

        try:
            # post_process_mask smooths the mask into clean, print-friendly edges.
            cutout = remove(rgba, session=self._session(), post_process_mask=True)
        except Exception as error:  # model load/inference errors come from onnxruntime
            self._logger.error("Background removal failed: %s", error)
            raise ImageBackgroundRemovalError() from error

        self._validate_cutout(cutout, expected_size=rgba.size)

        output = io.BytesIO()
        save_options: dict[str, bytes | str] = {"format": "PNG"}
        if icc_profile:
            save_options["icc_profile"] = icc_profile
        cutout.save(output, **save_options)
        return output.getvalue()

    def _validate_cutout(self, cutout: object, expected_size: tuple[int, int]) -> None:
        # rembg stacks several detected objects vertically, which would change
        # the canvas and break print placement — treat that as a failure.
        if not isinstance(cutout, Image.Image) or cutout.size != expected_size:
            raise ImageBackgroundRemovalError("Background removal changed the artwork size")

        alpha_histogram = cutout.getchannel("A").histogram()
        total = sum(alpha_histogram)
        foreground_ratio = (total - alpha_histogram[0]) / total if total else 0.0
        if foreground_ratio < self._min_foreground_ratio:
            raise ImageBackgroundRemovalError(
                "Background removal left almost nothing of the design; please try again"
            )
