from __future__ import annotations

import base64
from io import BytesIO

import pytest
from PIL import Image

from app.analyzers import comparison as comparison_module
from app.analyzers.comparison import compare_images
from app.errors import AnalysisError


def _image_bytes(size: tuple[int, int], mode: str, color, image_format: str = "PNG") -> bytes:
    image = Image.new(mode, size, color)
    buffer = BytesIO()
    image.save(buffer, format=image_format)
    return buffer.getvalue()


def _oriented_jpeg_bytes() -> bytes:
    image = Image.new("RGB", (16, 8), (20, 40, 60))
    exif = Image.Exif()
    exif[274] = 6
    buffer = BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


def _animated_gif_bytes() -> bytes:
    first = Image.new("RGB", (8, 8), (20, 40, 60))
    second = Image.new("RGB", (8, 8), (200, 40, 60))
    buffer = BytesIO()
    first.save(buffer, format="GIF", save_all=True, append_images=[second], loop=0)
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


def test_compare_handles_alpha_images() -> None:
    original = _image_bytes((8, 8), "RGBA", (20, 40, 60, 80))
    edited = _image_bytes((8, 8), "RGBA", (200, 40, 60, 180))

    metrics, _ = compare_images(original, edited)

    assert metrics.ssim < 1
    assert metrics.changed_area_ratio > 0


def test_compare_handles_16_bit_images() -> None:
    original = _image_bytes((8, 8), "I;16", 1024)
    edited = _image_bytes((8, 8), "I;16", 4096)

    metrics, _ = compare_images(original, edited)

    assert 0 <= metrics.ssim <= 1
    assert metrics.changed_area_ratio >= 0


def test_compare_handles_exif_orientation() -> None:
    image = _oriented_jpeg_bytes()

    metrics, _ = compare_images(image, image)

    assert metrics.ssim == 1
    assert metrics.phash_distance == 0


def test_compare_handles_large_aspect_ratio() -> None:
    original = _image_bytes((128, 2), "RGB", (20, 40, 60))
    edited = _image_bytes((2, 128), "RGB", (20, 40, 60))

    metrics, _ = compare_images(original, edited)

    assert 0 <= metrics.ssim <= 1
    assert 0 <= metrics.changed_area_ratio <= 1


def test_compare_uses_first_frame_of_animated_image() -> None:
    animated = _animated_gif_bytes()
    first_frame = _image_bytes((8, 8), "RGB", (20, 40, 60))

    metrics, _ = compare_images(animated, first_frame)

    assert metrics.ssim > 0.9
    assert 0 <= metrics.changed_area_ratio <= 1


def test_compare_rejects_truncated_jpeg(jpeg_bytes: bytes) -> None:
    with pytest.raises(AnalysisError) as error:
        compare_images(jpeg_bytes[:-16], jpeg_bytes)

    assert error.value.code == "invalid_image"


def test_compare_fallback_path(monkeypatch) -> None:
    monkeypatch.setattr(comparison_module, "cv2", None)
    monkeypatch.setattr(comparison_module, "imagehash", None)
    monkeypatch.setattr(comparison_module, "np", None)
    monkeypatch.setattr(comparison_module, "structural_similarity", None)

    original = _image_bytes((8, 8), "RGB", (20, 40, 60))
    edited = _image_bytes((8, 8), "RGB", (200, 40, 60))

    metrics, difference = compare_images(original, edited)

    assert metrics.ssim < 1
    assert metrics.phash_distance >= 0
    assert metrics.changed_area_ratio > 0
    assert base64.b64decode(difference.data_base64).startswith(b"\x89PNG")


def test_compare_rejects_invalid_image(jpeg_bytes: bytes) -> None:
    with pytest.raises(AnalysisError) as error:
        compare_images(b"not an image", jpeg_bytes)

    assert error.value.code == "invalid_image"
