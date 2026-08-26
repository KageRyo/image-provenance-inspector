"""Lossless privacy metadata sanitization that preserves provenance signals.

The sanitizer edits only selected EXIF privacy fields in JPEG, PNG, and WebP
containers. Other metadata blocks, including XMP, IPTC, software fields, and
C2PA data, are retained. A file containing C2PA is returned byte-for-byte
unchanged because changing a signed asset without re-signing it would damage
its provenance.
"""

from __future__ import annotations

import base64
import struct
import zlib
from collections.abc import Iterable
from dataclasses import dataclass
from io import BytesIO

from PIL import ExifTags, Image

from ..errors import AnalysisError
from ..models.result import (
    EncodedImage,
    ImageFileInfo,
    SanitizationGroup,
    SanitizationReport,
)
from . import c2pa, metadata
from .comparison import compare_images
from .image import inspect_image

_MIME_TYPES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}
_SUPPORTED_FORMATS = frozenset(_MIME_TYPES)
_ALL_GROUPS = frozenset(SanitizationGroup)

_OWNER_TAGS = frozenset(
    {
        "Artist",
        "Author",
        "Creator",
        "OwnerName",
        "XPAuthor",
    }
)
_COMMENT_TAGS = frozenset(
    {
        "Comment",
        "ImageDescription",
        "UserComment",
        "XPComment",
        "XPKeywords",
        "XPSubject",
        "XPTitle",
    }
)
_DEVICE_TAGS = frozenset(
    {
        "BodySerialNumber",
        "CameraOwnerName",
        "CameraSerialNumber",
        "DeviceSettingDescription",
        "HostComputer",
        "ImageUniqueID",
        "LensSerialNumber",
        "MakerNote",
        "MakerNoteSafety",
        "RawDataUniqueID",
        "UniqueCameraModel",
    }
)
_TIMESTAMP_TAGS = frozenset(
    {
        "DateTime",
        "DateTimeDigitized",
        "DateTimeOriginal",
        "OffsetTime",
        "OffsetTimeDigitized",
        "OffsetTimeOriginal",
        "SubsecTime",
        "SubsecTimeDigitized",
        "SubsecTimeOriginal",
    }
)


@dataclass(frozen=True)
class _JpegSegment:
    marker: int
    payload: bytes
    start: int
    end: int


def _requested_groups(groups: Iterable[SanitizationGroup] | None) -> frozenset[SanitizationGroup]:
    return frozenset(groups) if groups is not None else _ALL_GROUPS


def _tag_name(tag: int) -> str:
    return str(ExifTags.TAGS.get(tag, tag))


def _remove_tags(
    values: dict[int, object],
    *,
    prefix: str,
    groups: frozenset[SanitizationGroup],
    removed: list[str],
) -> None:
    for tag in list(values):
        name = _tag_name(tag)
        group: SanitizationGroup | None = None
        if name in _OWNER_TAGS:
            group = SanitizationGroup.OWNER
        elif name in _COMMENT_TAGS:
            group = SanitizationGroup.COMMENTS
        elif name in _DEVICE_TAGS:
            group = SanitizationGroup.DEVICE_IDENTIFIERS
        elif name in _TIMESTAMP_TAGS:
            group = SanitizationGroup.TIMESTAMPS
        if group in groups:
            del values[tag]
            removed.append(f"{prefix}:{name}")


def _filtered_exif(
    data: bytes,
    groups: frozenset[SanitizationGroup],
) -> tuple[bytes | None, list[str]]:
    """Return serialized filtered EXIF and the fields removed from it."""

    with Image.open(BytesIO(data)) as image:
        exif = image.getexif()
        if not exif:
            return None, []

        removed: list[str] = []
        if SanitizationGroup.GPS in groups and ExifTags.IFD.GPSInfo in exif:
            del exif[ExifTags.IFD.GPSInfo]
            exif._ifds.pop(ExifTags.IFD.GPSInfo, None)
            exif._hidden_data.pop(ExifTags.IFD.GPSInfo, None)
            removed.append("EXIF:GPSInfo")

        _remove_tags(exif._data, prefix="EXIF", groups=groups, removed=removed)
        if exif._info is not None:
            _remove_tags(exif._info, prefix="EXIF", groups=groups, removed=removed)

        if ExifTags.IFD.Exif in exif or ExifTags.IFD.Exif in exif._ifds:
            exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
            _remove_tags(exif_ifd, prefix="EXIF", groups=groups, removed=removed)
            if (
                "MakerNote" in {_tag_name(tag) for tag in exif_ifd}
                and SanitizationGroup.DEVICE_IDENTIFIERS in groups
            ):
                exif._ifds.pop(ExifTags.IFD.MakerNote, None)

        if SanitizationGroup.PRIVATE_THUMBNAILS in groups:
            has_thumbnail_ifd = bool(exif._info is not None and exif._info.next)
            if has_thumbnail_ifd:
                try:
                    thumbnail_ifd = exif.get_ifd(ExifTags.IFD.IFD1)
                except (AttributeError, KeyError, OSError, ValueError):
                    thumbnail_ifd = {}
                exif._ifds.pop(ExifTags.IFD.IFD1, None)
                if thumbnail_ifd:
                    removed.append("EXIF:PrivateThumbnail")

        if not removed:
            return None, []
        serialized = exif.tobytes()
        return serialized, removed


def _jpeg_segments(data: bytes) -> list[_JpegSegment]:
    if not data.startswith(b"\xff\xd8"):
        return []
    segments: list[_JpegSegment] = []
    position = 2
    while position + 1 < len(data):
        if data[position] != 0xFF:
            break
        start = position
        while position < len(data) and data[position] == 0xFF:
            position += 1
        if position >= len(data):
            break
        marker = data[position]
        position += 1
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            segments.append(_JpegSegment(marker, b"", start, position))
            if marker == 0xD9:
                break
            continue
        if position + 2 > len(data):
            break
        length = struct.unpack_from(">H", data, position)[0]
        end = position + length
        if length < 2 or end > len(data):
            break
        segments.append(_JpegSegment(marker, data[position + 2 : end], start, end))
        position = end
        if marker == 0xDA:
            break
    return segments


def _jpeg_segment(marker: int, payload: bytes) -> bytes:
    if len(payload) + 2 > 0xFFFF:
        raise AnalysisError(
            code="sanitization_failed",
            message="The image metadata block is too large to rewrite safely.",
            status_code=422,
        )
    return b"\xff" + bytes([marker]) + struct.pack(">H", len(payload) + 2) + payload


def _rewrite_jpeg(data: bytes, exif: bytes | None) -> bytes:
    segments = _jpeg_segments(data)
    if not segments:
        return data
    output = bytearray(data[:2])
    replaced = False
    for segment in segments:
        if segment.marker == 0xDA:
            output.extend(data[segment.start :])
            break
        is_exif = segment.marker == 0xE1 and segment.payload.startswith(b"Exif\x00\x00")
        if is_exif:
            if not replaced and exif is not None:
                output.extend(_jpeg_segment(0xE1, exif))
            replaced = True
        else:
            output.extend(data[segment.start : segment.end])
    return bytes(output)


def _png_chunks(data: bytes) -> list[tuple[int, int, bytes, bytes]]:
    signature = b"\x89PNG\r\n\x1a\n"
    if not data.startswith(signature):
        return []
    chunks: list[tuple[int, int, bytes, bytes]] = []
    position = len(signature)
    while position + 12 <= len(data):
        length = struct.unpack_from(">I", data, position)[0]
        end = position + 12 + length
        if end > len(data):
            break
        chunk_type = data[position + 4 : position + 8]
        payload = data[position + 8 : position + 8 + length]
        chunks.append((position, end, chunk_type, payload))
        position = end
        if chunk_type == b"IEND":
            break
    return chunks


def _png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    body = chunk_type + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def _rewrite_png(data: bytes, exif: bytes | None) -> bytes:
    chunks = _png_chunks(data)
    if not chunks:
        return data
    output = bytearray(data[:8])
    replaced = False
    for start, end, chunk_type, _payload in chunks:
        if chunk_type == b"eXIf":
            if not replaced and exif is not None:
                payload_without_prefix = exif[6:] if exif.startswith(b"Exif\x00\x00") else exif
                output.extend(_png_chunk(chunk_type, payload_without_prefix))
            replaced = True
        else:
            output.extend(data[start:end])
    return bytes(output)


def _webp_chunks(data: bytes) -> list[tuple[int, int, bytes, bytes]]:
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return []
    chunks: list[tuple[int, int, bytes, bytes]] = []
    position = 12
    while position + 8 <= len(data):
        chunk_type = data[position : position + 4]
        length = struct.unpack_from("<I", data, position + 4)[0]
        end = position + 8 + length + (length & 1)
        if end > len(data):
            break
        payload = data[position + 8 : position + 8 + length]
        chunks.append((position, end, chunk_type, payload))
        position = end
    return chunks


def _webp_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    chunk = chunk_type + struct.pack("<I", len(payload)) + payload
    return chunk + (b"\x00" if len(payload) & 1 else b"")


def _rewrite_webp(data: bytes, exif: bytes | None) -> bytes:
    chunks = _webp_chunks(data)
    if not chunks:
        return data
    output = bytearray(data[:12])
    replaced = False
    for start, end, chunk_type, _payload in chunks:
        if chunk_type == b"EXIF":
            if not replaced and exif is not None:
                payload_without_prefix = exif[6:] if exif.startswith(b"Exif\x00\x00") else exif
                output.extend(_webp_chunk(chunk_type, payload_without_prefix))
            replaced = True
        else:
            output.extend(data[start:end])
    struct.pack_into("<I", output, 4, len(output) - 8)
    return bytes(output)


def _metadata_chunks_contain_c2pa(data: bytes, image_format: str) -> bool:
    marker = b"c2pa"
    if image_format == "JPEG":
        segments = _jpeg_segments(data)
        return any(
            marker in segment.payload.lower() or b"jumbf" in segment.payload.lower()
            for segment in segments
        )
    if image_format == "PNG":
        chunks = _png_chunks(data)
        return any(
            chunk_type not in {b"IDAT", b"fdAT"}
            and (
                marker in payload.lower()
                or b"jumbf" in payload.lower()
                or chunk_type in {b"caBX", b"c2pa"}
            )
            for _, _, chunk_type, payload in chunks
        )
    if image_format == "WEBP":
        chunks = _webp_chunks(data)
        return any(
            chunk_type not in {b"VP8 ", b"VP8L", b"VP8X", b"ALPH"}
            and (marker in payload.lower() or b"jumbf" in payload.lower() or chunk_type == b"C2PA")
            for _, _, chunk_type, payload in chunks
        )
    return False


def _rewrite_container(data: bytes, image_format: str, exif: bytes | None) -> bytes:
    if image_format == "JPEG":
        return _rewrite_jpeg(data, exif)
    if image_format == "PNG":
        return _rewrite_png(data, exif)
    if image_format == "WEBP":
        return _rewrite_webp(data, exif)
    return data


def _preserved_metadata(data: bytes, c2pa_present: bool) -> list[str]:
    summary = metadata.extract_metadata(data)
    preserved: list[str] = []
    if c2pa_present:
        preserved.append("C2PA Content Credentials")
    if summary.xmp:
        preserved.append("XMP, including any provenance fields")
    if summary.iptc:
        preserved.append("IPTC, including any provenance fields")
    if summary.software:
        preserved.append("Software/CreatorTool")
    if summary.camera:
        preserved.append("Camera make/model")
    return preserved


def sanitize_image(
    data: bytes,
    groups: Iterable[SanitizationGroup] | None = None,
) -> tuple[bytes, SanitizationReport]:
    """Remove selected privacy EXIF fields while retaining provenance blocks."""

    source_info, _ = inspect_image(data)
    if source_info.format not in _SUPPORTED_FORMATS:
        supported = ", ".join(sorted(_SUPPORTED_FORMATS))
        raise AnalysisError(
            code="unsupported_sanitization_format",
            message=f"Privacy sanitization currently supports: {supported}.",
            status_code=422,
        )

    requested = _requested_groups(groups)
    mime_type = _MIME_TYPES[source_info.format]
    c2pa_summary = c2pa.inspect_c2pa(data, mime_type)
    c2pa_present = c2pa_summary.present or _metadata_chunks_contain_c2pa(data, source_info.format)
    preserved = _preserved_metadata(data, c2pa_present)
    warnings = [
        "C2PA, XMP, IPTC, software fields, and other provenance signals are preserved.",
    ]

    if c2pa_present:
        warnings.append(
            "C2PA Content Credentials detected; the file was left byte-for-byte unchanged "
            "to avoid invalidating its provenance."
        )
        report = SanitizationReport(
            sanitized=False,
            c2pa_present=True,
            c2pa_preserved=True,
            pixel_content_changed=False,
            preserved=preserved,
            warnings=warnings,
        )
        return data, report

    filtered_exif, removed = _filtered_exif(data, requested)
    output_data = _rewrite_container(data, source_info.format, filtered_exif) if removed else data
    if output_data == data:
        warnings.append("No selected privacy metadata was found; the original bytes were retained.")
        report = SanitizationReport(
            sanitized=False,
            c2pa_present=False,
            c2pa_preserved=True,
            pixel_content_changed=False,
            removed=removed,
            preserved=preserved,
            warnings=warnings,
        )
        return data, report

    metrics, _ = compare_images(data, output_data)
    report = SanitizationReport(
        sanitized=True,
        c2pa_present=False,
        c2pa_preserved=True,
        pixel_content_changed=metrics.changed_area_ratio > 0,
        removed=removed,
        preserved=preserved,
        warnings=warnings,
        comparison=metrics,
    )
    return output_data, report


def build_sanitize_payload(
    original_data: bytes,
    output_data: bytes,
) -> tuple[ImageFileInfo, ImageFileInfo, EncodedImage]:
    original_info, _ = inspect_image(original_data)
    output_info, _ = inspect_image(output_data)
    mime_type = _MIME_TYPES.get(output_info.format, "application/octet-stream")
    encoded = EncodedImage(
        mime_type=mime_type,
        data_base64=base64.b64encode(output_data).decode("ascii"),
    )
    return original_info, output_info, encoded
