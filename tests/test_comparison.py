from __future__ import annotations

import base64
from io import BytesIO

import pytest
from PIL import Image

from app.analyzers.comparison import compare_images
from app.errors import AnalysisError


def _image_bytes(size: tuple[int, int], mode: str, color, image_format: str = "PNG") -> bytes:
    image = Image.new(mode, size, color)
    buffer = BytesIO()
    image.save(buffer, format=image_format)
    return buffer.getvalue()


def test_identical_images_have_high_similarity(jpeg_bytes: bytes) -> None:
    metrics, difference = compare_images(jpeg_bytes, jpeg_bytes)

    assert metrics.ssim == 1
    assert metrics.phash_distance == 0
    assert metrics.changed_area_ratio == 0
    assert base64.b64decode(difference.data_base64).startswith(b"\x89PNG")


def test_changed_images_report_difference(jpeg_bytes: bytes, changed_jpeg_bytes: bytes) -> None:
    metrics, _ = compare_images(jpeg_bytes, changed_jpeg_bytes)

    assert metrics.ssim < 1
    assert metrics.phash_distance >= 0
    assert metrics.changed_area_ratio > 0


def test_compare_handles_different_resolution_and_aspect_ratio() -> None:
    original = _image_bytes((16, 8), "RGB", (20, 40, 60))
    edited = _image_bytes((8, 16), "RGBA", (20, 40, 60, 255))

    metrics, _ = compare_images(original, edited)

    assert 0 <= metrics.ssim <= 1
    assert 0 <= metrics.changed_area_ratio <= 1


def test_compare_handles_grayscale_images() -> None:
    image = _image_bytes((8, 8), "L", 128)

    metrics, _ = compare_images(image, image)

    assert metrics.ssim == 1
    assert metrics.phash_distance == 0
    assert metrics.changed_area_ratio == 0


def test_compare_handles_very_small_images() -> None:
    original = _image_bytes((1, 1), "RGB", (0, 0, 0))
    edited = _image_bytes((1, 1), "RGB", (255, 255, 255))

    metrics, _ = compare_images(original, edited)

    assert metrics.ssim < 1
    assert metrics.changed_area_ratio == 1


def test_compare_rejects_invalid_image(jpeg_bytes: bytes) -> None:
    with pytest.raises(AnalysisError) as error:
        compare_images(b"not an image", jpeg_bytes)

    assert error.value.code == "invalid_image"
