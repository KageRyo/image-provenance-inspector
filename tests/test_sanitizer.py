from __future__ import annotations

import struct
from io import BytesIO
from pathlib import Path

from PIL import ExifTags, Image

from app.analyzers.metadata import extract_metadata
from app.analyzers.sanitizer import sanitize_image
from app.models.result import SanitizationGroup

REPOSITORY_ROOT = Path(__file__).parents[1]


def _privacy_image(image_format: str = "JPEG") -> bytes:
    image = Image.new("RGB", (24, 16), (40, 100, 180))
    exif = Image.Exif()
    exif[271] = "ExampleCam"
    exif[272] = "Model 1"
    exif[315] = "Private Owner"
    exif[36867] = "2026:08:20 15:32:11"
    exif[34853] = {1: "N", 2: (1, 2, 3), 3: "E", 4: (4, 5, 6)}
    exif[34665] = {42033: "PRIVATE-SERIAL", 37510: b"private comment"}
    buffer = BytesIO()
    save_options = {"exif": exif}
    if image_format == "WEBP":
        save_options["lossless"] = True
    image.save(buffer, format=image_format, **save_options)
    return buffer.getvalue()


def _add_jpeg_xmp(data: bytes) -> bytes:
    payload = (
        b"http://ns.adobe.com/xap/1.0/\x00"
        b'<x:xmpmeta><rdf:Description AI-assisted="true" /></x:xmpmeta>'
    )
    segment = b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload
    return data[:2] + segment + data[2:]


def test_sanitizer_removes_selected_privacy_exif_and_preserves_pixels() -> None:
    source = _privacy_image()

    output, report = sanitize_image(source)

    assert report.sanitized is True
    assert report.c2pa_present is False
    assert report.c2pa_preserved is True
    assert report.pixel_content_changed is False
    assert "EXIF:GPSInfo" in report.removed
    assert "EXIF:Artist" in report.removed
    assert "EXIF:BodySerialNumber" in report.removed
    assert "EXIF:UserComment" in report.removed
    assert "EXIF:PrivateThumbnail" not in report.removed
    assert report.comparison is not None
    assert report.comparison.changed_area_ratio == 0

    with Image.open(BytesIO(output)) as image:
        exif = image.getexif()
        assert exif[271] == "ExampleCam"
        assert exif[272] == "Model 1"
        assert ExifTags.IFD.GPSInfo not in exif
        assert 315 not in exif
        assert 36867 not in exif
        assert exif.get_ifd(ExifTags.IFD.Exif) == {}

    extracted = extract_metadata(output)
    assert extracted.camera == "ExampleCam Model 1"
    assert extracted.captured_at is None


def test_sanitizer_honors_selected_groups() -> None:
    source = _privacy_image()

    output, report = sanitize_image(source, [SanitizationGroup.GPS])

    assert report.removed == ["EXIF:GPSInfo"]
    with Image.open(BytesIO(output)) as image:
        exif = image.getexif()
        assert ExifTags.IFD.GPSInfo not in exif
        assert exif[315] == "Private Owner"
        assert exif[36867] == "2026:08:20 15:32:11"


def test_sanitizer_preserves_xmp_blocks() -> None:
    source = _add_jpeg_xmp(_privacy_image())

    output, report = sanitize_image(source)

    assert b'AI-assisted="true"' in output
    assert "XMP, including any provenance fields" in report.preserved
    assert extract_metadata(output).xmp is True


def test_sanitizer_leaves_c2pa_asset_unchanged() -> None:
    source = (REPOSITORY_ROOT / "fixtures" / "official-c2pa" / "C.jpg").read_bytes()

    output, report = sanitize_image(source)

    assert output == source
    assert report.sanitized is False
    assert report.c2pa_present is True
    assert report.c2pa_preserved is True
    assert report.removed == []
    assert any("byte-for-byte unchanged" in warning for warning in report.warnings)


def test_sanitizer_supports_png_and_webp_without_reencoding_pixels() -> None:
    for image_format in ("PNG", "WEBP"):
        source = _privacy_image(image_format)

        output, report = sanitize_image(source)

        assert report.sanitized is True
        assert report.pixel_content_changed is False
        assert report.comparison is not None
        assert report.comparison.changed_area_ratio == 0
