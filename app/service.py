"""Application service that composes the independent analyzers."""

from __future__ import annotations

from .analyzers import c2pa, image, metadata
from .models.result import AnalysisResult, CaptureInfo, MetadataSummary
from .provenance.rules import classify_provenance

_MIME_TYPES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
    "GIF": "image/gif",
    "TIFF": "image/tiff",
    "BMP": "image/bmp",
}


class AnalysisService:
    """Orchestrate metadata, C2PA, and provenance analysis."""

    def analyze(self, data: bytes) -> AnalysisResult:
        file_info, _ = image.inspect_image(data)
        extracted_metadata = metadata.extract_metadata(data)
        c2pa_summary = c2pa.inspect_c2pa(
            data, _MIME_TYPES.get(file_info.format, "application/octet-stream")
        )
        assessment = classify_provenance(
            camera=extracted_metadata.camera,
            software=extracted_metadata.software,
            c2pa=c2pa_summary,
        )
        return AnalysisResult(
            file=file_info,
            capture=CaptureInfo(
                camera=extracted_metadata.camera,
                captured_at=extracted_metadata.captured_at,
            ),
            metadata=MetadataSummary(
                exif=extracted_metadata.exif,
                xmp=extracted_metadata.xmp,
                iptc=extracted_metadata.iptc,
                software=extracted_metadata.software,
            ),
            c2pa=c2pa_summary,
            assessment=assessment,
        )
