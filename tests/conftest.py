from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image


@pytest.fixture
def jpeg_bytes() -> bytes:
    image = Image.new("RGB", (64, 48), (40, 100, 180))
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


@pytest.fixture
def changed_jpeg_bytes(jpeg_bytes: bytes) -> bytes:
    image = Image.open(BytesIO(jpeg_bytes)).convert("RGB")
    for x in range(16, 32):
        for y in range(12, 28):
            image.putpixel((x, y), (220, 30, 30))
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()
