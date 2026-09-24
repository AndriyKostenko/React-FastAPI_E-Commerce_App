"""
RembgBackgroundRemover against the real ONNX model — no inference is mocked.

The first run downloads the model (~170 MB) into rembg's cache (REMBG_HOME,
default ~/.u2net); later runs load it from disk.
"""
import base64
import io
from logging import getLogger

import pytest
from PIL import Image, ImageDraw

from exceptions.image_generation_exceptions import ImageBackgroundRemovalError
from service_layer.background_removal_service import RembgBackgroundRemover
from shared.settings import get_settings


def _design_on_flat_background(size: int = 1024) -> str:
    """A bold two-colour badge on a flat white backdrop, as the prompt asks for."""
    image = Image.new("RGB", (size, size), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    margin = size // 4
    draw.ellipse((margin, margin, size - margin, size - margin), fill=(200, 30, 60))
    draw.rectangle((size // 2 - size // 12, margin, size // 2 + size // 12, size - margin), fill=(20, 40, 160))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def _decode(data_url: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(data_url.partition(",")[2])))


@pytest.fixture(scope="module")
def remover() -> RembgBackgroundRemover:
    return RembgBackgroundRemover(settings=get_settings(), logger=getLogger("test"))


async def test_backdrop_becomes_transparent_and_design_stays_opaque(remover: RembgBackgroundRemover):
    cutout = _decode(await remover.remove(_design_on_flat_background()))

    assert cutout.mode == "RGBA"
    assert cutout.size == (1024, 1024)
    alpha = cutout.getchannel("A")
    assert alpha.getpixel((10, 10)) == 0            # corner backdrop removed
    assert alpha.getpixel((512, 512)) == 255        # centre of the badge kept
    assert cutout.getpixel((512, 512))[:3] == (20, 40, 160)


class TestCutoutValidation:
    """Guards that turn an unprintable cutout into a failed job."""

    def test_empty_cutout_is_rejected(self, remover: RembgBackgroundRemover):
        empty = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        with pytest.raises(ImageBackgroundRemovalError):
            remover._validate_cutout(empty, expected_size=(100, 100))

    def test_resized_cutout_is_rejected(self, remover: RembgBackgroundRemover):
        stacked = Image.new("RGBA", (100, 200), (255, 0, 0, 255))
        with pytest.raises(ImageBackgroundRemovalError):
            remover._validate_cutout(stacked, expected_size=(100, 100))

    def test_cutout_with_enough_foreground_passes(self, remover: RembgBackgroundRemover):
        cutout = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        cutout.paste((255, 0, 0, 255), (0, 0, 20, 20))   # 4% opaque
        remover._validate_cutout(cutout, expected_size=(100, 100))
