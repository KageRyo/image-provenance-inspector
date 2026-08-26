"""Application errors mapped to the public error schema."""

from dataclasses import dataclass, field

from .models.result import ErrorDetail


@dataclass
class AnalysisError(Exception):
    """An expected user-facing error raised by an analyzer or API service."""

    code: str
    message: str
    status_code: int = 400
    details: list[ErrorDetail] = field(default_factory=list)

    def __post_init__(self) -> None:
        super().__init__(self.message)


def invalid_image_error(
    message: str = "The uploaded file is not a supported image.",
) -> AnalysisError:
    return AnalysisError(code="invalid_image", message=message, status_code=422)
