"""Metadata extraction with ExifTool support and a Pillow fallback.

ExifTool is deliberately invoked with stdin and an argument list rather than a
shell command. This keeps uploaded filenames out of command execution and
allows the service to work in lightweight environments where ExifTool is not
installed.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from typing import Any

from PIL import ExifTags, Image


@dataclass(frozen=True)
class ExtractedMetadata:
    exif: bool
    xmp: bool
    iptc: bool
    software: str | None
    camera: str | None
    captured_at: datetime | None


_DATE_FORMATS = (
    "%Y:%m:%d %H:%M:%S%z",
    "%Y:%m:%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S%z",
    "%Y-%m-%d %H:%M:%S",
)
_XMP_MARKERS = (b"<x:xmpmeta", b"<xmpmeta", b"http://ns.adobe.com/xap/1.0/")
_SOFTWARE_KEYS = (
    "Software",
    "CreatorTool",
    "XMP:CreatorTool",
    "XMP:Software",
    "EXIF:Software",
)
_CAMERA_KEYS = (
    ("Make", "Model"),
    ("EXIF:Make", "EXIF:Model"),
)
_CAPTURE_KEYS = (
    "DateTimeOriginal",
    "DateTimeDigitized",
    "DateTime",
    "EXIF:DateTimeOriginal",
    "EXIF:CreateDate",
)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _first_value(values: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = _text(values.get(key))
        if value:
            return value
    return None


def _parse_datetime(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    for date_format in _DATE_FORMATS:
        try:
            return datetime.strptime(normalized, date_format)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _camera_from_values(values: dict[str, Any]) -> str | None:
    for make_key, model_key in _CAMERA_KEYS:
        make = _text(values.get(make_key))
        model = _text(values.get(model_key))
        if make and model:
            if model.casefold().startswith(make.casefold()):
                return model
            return f"{make} {model}"
        if model or make:
            return model or make
    return None


def _from_exiftool(data: bytes) -> ExtractedMetadata | None:
    executable = shutil.which("exiftool")
    if executable is None:
        return None
    try:
        completed = subprocess.run(
            [executable, "-j", "-"],
            input=data,
            capture_output=True,
            check=True,
            timeout=5,
        )
        payload = json.loads(completed.stdout)
        values = payload[0] if isinstance(payload, list) and payload else {}
        if not isinstance(values, dict):
            return None
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError):
        return None

    exif = any(key.startswith("EXIF:") for key in values) or any(
        key in values for key in ("Make", "Model", "DateTimeOriginal", "Software")
    )
    xmp = any(key.startswith("XMP:") for key in values)
    iptc = any(key.startswith("IPTC:") for key in values)
    software = _first_value(values, _SOFTWARE_KEYS)
    capture_value = _first_value(values, _CAPTURE_KEYS)
    return ExtractedMetadata(
        exif=exif,
        xmp=xmp,
        iptc=iptc,
        software=software,
        camera=_camera_from_values(values),
        captured_at=_parse_datetime(capture_value),
    )


def _from_pillow(data: bytes) -> ExtractedMetadata:
    with Image.open(BytesIO(data)) as image:
        exif_data = image.getexif()
        values: dict[str, Any] = {}
        for tag, value in exif_data.items():
            values[ExifTags.TAGS.get(tag, str(tag))] = value

        xmp_data = image.info.get("XML:com.adobe.xmp") or image.info.get("xmp")
        if isinstance(xmp_data, str):
            xmp_bytes = xmp_data.encode()
        else:
            xmp_bytes = xmp_data or b""
        xmp = any(marker in xmp_bytes for marker in _XMP_MARKERS)
        if xmp:
            creator_match = re.search(rb"(?:CreatorTool|Software)>([^<]+)<", xmp_bytes)
            if creator_match:
                values["CreatorTool"] = creator_match.group(1).decode(errors="replace")

        iptc = any(key.lower() in {"iptc", "photoshop"} for key in image.info)
        return ExtractedMetadata(
            exif=bool(exif_data),
            xmp=xmp,
            iptc=iptc,
            software=_first_value(values, ("Software", "CreatorTool")),
            camera=_camera_from_values(values),
            captured_at=_parse_datetime(
                _first_value(values, ("DateTimeOriginal", "DateTimeDigitized", "DateTime"))
            ),
        )


def extract_metadata(data: bytes) -> ExtractedMetadata:
    """Extract the stable metadata summary from image bytes."""

    return _from_exiftool(data) or _from_pillow(data)
