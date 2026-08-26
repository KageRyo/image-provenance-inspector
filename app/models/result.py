"""Stable Pydantic schemas shared by the API, CLI, and UI.

The API intentionally exposes a small, explicit contract. Internal analyzer
details must be translated into these models before they leave the application.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SchemaModel(BaseModel):
    """Base model that rejects accidental fields in the public JSON contract."""

    model_config = ConfigDict(extra="forbid")


class OriginType(StrEnum):
    CAMERA_CAPTURED = "CAMERA_CAPTURED"
    SYNTHETIC = "SYNTHETIC"
    UNKNOWN = "UNKNOWN"


class EditingType(StrEnum):
    NONE_DETECTED = "NONE_DETECTED"
    TRADITIONAL = "TRADITIONAL"
    GENERATIVE = "GENERATIVE"
    UNKNOWN = "UNKNOWN"


class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SanitizationGroup(StrEnum):
    """Privacy metadata groups that may be removed without touching provenance."""

    GPS = "gps"
    DEVICE_IDENTIFIERS = "device-identifiers"
    OWNER = "owner"
    COMMENTS = "comments"
    PRIVATE_THUMBNAILS = "private-thumbnails"
    TIMESTAMPS = "timestamps"


class ImageFileInfo(SchemaModel):
    format: str = Field(min_length=1, max_length=32)
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CaptureInfo(SchemaModel):
    camera: str | None = Field(default=None, max_length=512)
    captured_at: datetime | None = None


class MetadataSummary(SchemaModel):
    exif: bool
    xmp: bool
    iptc: bool
    software: str | None = Field(default=None, max_length=512)


class C2PASummary(SchemaModel):
    present: bool
    valid: bool | None
    claim_generator: str | None = Field(default=None, max_length=512)
    actions: list[str] = Field(default_factory=list, max_length=50)
    generative_edit: bool


class OriginAssessment(SchemaModel):
    type: OriginType
    confidence: Confidence
    reason: list[str] = Field(min_length=1, max_length=20)


class EditingAssessment(SchemaModel):
    type: EditingType
    confidence: Confidence
    reason: list[str] = Field(min_length=1, max_length=20)


class Assessment(SchemaModel):
    origin: OriginAssessment
    editing: EditingAssessment


class AnalysisResult(SchemaModel):
    file: ImageFileInfo
    capture: CaptureInfo
    metadata: MetadataSummary
    c2pa: C2PASummary
    assessment: Assessment


class CompareMetrics(SchemaModel):
    ssim: float = Field(ge=0, le=1)
    phash_distance: int = Field(ge=0)
    changed_area_ratio: float = Field(ge=0, le=1)


class DifferenceImage(SchemaModel):
    mime_type: str = Field(pattern=r"^image/png$")
    data_base64: str = Field(min_length=1)


class CompareResult(SchemaModel):
    original: ImageFileInfo
    edited: ImageFileInfo
    metrics: CompareMetrics
    difference: DifferenceImage


class EncodedImage(SchemaModel):
    mime_type: str = Field(pattern=r"^image/[a-z0-9.+-]+$")
    data_base64: str = Field(min_length=1)


class SanitizationReport(SchemaModel):
    sanitized: bool
    c2pa_present: bool
    c2pa_preserved: bool
    pixel_content_changed: bool
    removed: list[str] = Field(default_factory=list, max_length=100)
    preserved: list[str] = Field(default_factory=list, max_length=100)
    warnings: list[str] = Field(default_factory=list, max_length=20)
    comparison: CompareMetrics | None = None


class SanitizeResult(SchemaModel):
    original: ImageFileInfo
    output: ImageFileInfo
    image: EncodedImage
    report: SanitizationReport


class ErrorDetail(SchemaModel):
    location: list[str | int] = Field(default_factory=list)
    message: str
    type: str


class ErrorResponse(SchemaModel):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)


class HealthResponse(SchemaModel):
    status: str = Field(pattern=r"^ok$")
