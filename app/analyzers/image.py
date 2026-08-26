"""Basic image inspection shared by analyze and compare endpoints."""

from __future__ import annotations

import hashlib
from io import BytesIO

from PIL import Image, UnidentifiedImageError

from ..errors import invalid_image_error
from ..models.result import ImageFileInfo


def open_image(data: bytes) -> Image.Image:
    """Open and fully load an uploaded image, translating Pillow errors."""

    try:
        with Image.open(BytesIO(data)) as image:
            image.load()
            detached = image.copy()
            detached.format = image.format
            return detached
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise invalid_image_error() from exc


def inspect_image(data: bytes) -> tuple[ImageFileInfo, Image.Image]:
    """Return stable file information and a detached Pillow image."""

    image = open_image(data)
    image_format = (image.format or "unknown").upper()
    digest = hashlib.sha256(data).hexdigest()
    info = ImageFileInfo(
        format=image_format,
        width=image.width,
        height=image.height,
        size_bytes=len(data),
        sha256=digest,
    )
    return info, image
