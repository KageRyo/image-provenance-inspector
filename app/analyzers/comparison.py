"""Original-versus-edited image comparison metrics."""

from __future__ import annotations

import base64
import math
from io import BytesIO

from PIL import Image

try:  # Optional acceleration for larger production workloads.
    import cv2
    import imagehash
    import numpy as np
    from skimage.metrics import structural_similarity
except ImportError:  # pragma: no cover - exercised by the lightweight install
    cv2 = None
    imagehash = None
    np = None
    structural_similarity = None

from ..models.result import CompareMetrics, DifferenceImage
from .image import open_image


def _rgb_array(image: Image.Image):
    if np is None:
        return None
    return np.asarray(image.convert("RGB"), dtype=np.uint8)


def _png_base64(mask: Image.Image | object) -> str:
    if cv2 is not None and np is not None:
        ok, encoded = cv2.imencode(".png", mask)
        if not ok:
            raise ValueError("Unable to encode the difference mask")
        return base64.b64encode(encoded.tobytes()).decode("ascii")
    buffer = BytesIO()
    mask.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _resize_for_compare(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return image.resize(size, Image.Resampling.LANCZOS) if image.size != size else image


def _fallback_grayscale(image: Image.Image) -> list[float]:
    return [float(value) for value in image.convert("L").getdata()]


def _fallback_ssim(first: list[float], second: list[float]) -> float:
    count = len(first)
    mean_first = sum(first) / count
    mean_second = sum(second) / count
    variance_first = sum((value - mean_first) ** 2 for value in first) / count
    variance_second = sum((value - mean_second) ** 2 for value in second) / count
    covariance = (
        sum(
            (first_value - mean_first) * (second_value - mean_second)
            for first_value, second_value in zip(first, second, strict=True)
        )
        / count
    )
    c1 = 6.5025
    c2 = 58.5225
    numerator = (2 * mean_first * mean_second + c1) * (2 * covariance + c2)
    denominator = (mean_first**2 + mean_second**2 + c1) * (variance_first + variance_second + c2)
    return numerator / denominator if denominator else 1.0


def _fallback_phash(image: Image.Image) -> str:
    """Compute a compact DCT perceptual hash without optional native packages."""

    grayscale = image.convert("L").resize((32, 32), Image.Resampling.LANCZOS)
    pixels = [float(value) for value in grayscale.getdata()]
    coefficients: list[float] = []
    for row in range(8):
        for column in range(8):
            coefficient = 0.0
            for y in range(32):
                for x in range(32):
                    coefficient += (
                        pixels[y * 32 + x]
                        * math.cos(math.pi * (2 * x + 1) * column / 64)
                        * math.cos(math.pi * (2 * y + 1) * row / 64)
                    )
            alpha_x = 1 / math.sqrt(2) if column == 0 else 1.0
            alpha_y = 1 / math.sqrt(2) if row == 0 else 1.0
            coefficients.append(coefficient * alpha_x * alpha_y / 16)
    average = sum(coefficients[1:]) / 63
    return "".join("1" if value > average else "0" for value in coefficients[1:])


def _fallback_phash_distance(first: Image.Image, second: Image.Image) -> int:
    first_hash = _fallback_phash(first)
    second_hash = _fallback_phash(second)
    return sum(left != right for left, right in zip(first_hash, second_hash, strict=True))


def _fallback_difference(first: Image.Image, second: Image.Image) -> tuple[float, Image.Image]:
    first_rgb = list(first.convert("RGB").getdata())
    second_rgb = list(second.convert("RGB").getdata())
    changed = [
        255
        if max(abs(left - right) for left, right in zip(first_pixel, second_pixel, strict=True))
        > 16
        else 0
        for first_pixel, second_pixel in zip(first_rgb, second_rgb, strict=True)
    ]
    mask = Image.new("L", first.size)
    mask.putdata(changed)
    ratio = sum(value > 0 for value in changed) / len(changed)
    return ratio, mask


def compare_images(
    original_data: bytes, edited_data: bytes
) -> tuple[CompareMetrics, DifferenceImage]:
    """Calculate perceptual similarity and return a PNG difference mask."""

    original = open_image(original_data)
    edited = open_image(edited_data)
    edited_for_compare_image = _resize_for_compare(edited, original.size)

    if cv2 is not None and np is not None and structural_similarity is not None:
        original_rgb = _rgb_array(original)
        edited_rgb = _rgb_array(edited_for_compare_image)
        original_gray = cv2.cvtColor(original_rgb, cv2.COLOR_RGB2GRAY)
        edited_gray = cv2.cvtColor(edited_rgb, cv2.COLOR_RGB2GRAY)
        ssim = float(structural_similarity(original_gray, edited_gray, data_range=255))
        pixel_difference = cv2.absdiff(original_rgb, edited_rgb)
        channel_difference = np.max(pixel_difference, axis=2)
        mask = np.where(channel_difference > 16, 255, 0).astype(np.uint8)
        changed_area_ratio = float(np.count_nonzero(mask) / mask.size)
    else:
        original_gray = _fallback_grayscale(original)
        edited_gray = _fallback_grayscale(edited_for_compare_image)
        ssim = _fallback_ssim(original_gray, edited_gray)
        changed_area_ratio, mask = _fallback_difference(original, edited_for_compare_image)

    if imagehash is not None:
        original_hash = imagehash.phash(original)
        edited_hash = imagehash.phash(edited)
        phash_distance = int(original_hash - edited_hash)
    else:
        phash_distance = _fallback_phash_distance(original, edited)

    metrics = CompareMetrics(
        ssim=round(max(0.0, min(1.0, ssim)), 6),
        phash_distance=phash_distance,
        changed_area_ratio=round(max(0.0, min(1.0, changed_area_ratio)), 6),
    )
    difference = DifferenceImage(mime_type="image/png", data_base64=_png_base64(mask))
    return metrics, difference
