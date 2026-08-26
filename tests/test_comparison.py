from __future__ import annotations

import base64

from app.analyzers.comparison import compare_images


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
