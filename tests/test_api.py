from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models.result import AnalysisResult, CompareResult, ErrorResponse

client = TestClient(app)


def test_analyze_returns_pydantic_contract(jpeg_bytes: bytes) -> None:
    response = client.post(
        "/api/v1/analyze",
        files={"image": ("sample.jpg", jpeg_bytes, "image/jpeg")},
    )

    assert response.status_code == 200
    payload = response.json()
    AnalysisResult.model_validate(payload)
    assert set(payload) == {"file", "capture", "metadata", "c2pa", "assessment"}
    assert payload["file"]["format"] == "JPEG"
    assert payload["c2pa"]["present"] is False
    assert payload["assessment"]["type"] == "UNKNOWN"


def test_compare_returns_metrics_and_difference(
    jpeg_bytes: bytes, changed_jpeg_bytes: bytes
) -> None:
    response = client.post(
        "/api/v1/compare",
        files={
            "original": ("original.jpg", jpeg_bytes, "image/jpeg"),
            "edited": ("edited.jpg", changed_jpeg_bytes, "image/jpeg"),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    CompareResult.model_validate(payload)
    assert set(payload) == {"original", "edited", "metrics", "difference"}
    assert payload["metrics"]["changed_area_ratio"] > 0
    assert payload["difference"]["mime_type"] == "image/png"


def test_invalid_upload_uses_error_schema() -> None:
    response = client.post(
        "/api/v1/analyze",
        files={"image": ("not-an-image.txt", b"not an image", "text/plain")},
    )

    assert response.status_code == 422
    ErrorResponse.model_validate(response.json())
    assert set(response.json()) == {"code", "message", "details"}
    assert response.json()["code"] == "invalid_image"


def test_missing_upload_uses_error_schema() -> None:
    response = client.post("/api/v1/analyze")

    assert response.status_code == 422
    ErrorResponse.model_validate(response.json())
    assert response.json()["code"] == "validation_error"
