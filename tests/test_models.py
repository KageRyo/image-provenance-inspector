from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.result import AnalysisResult


def test_analysis_contract_rejects_unknown_fields() -> None:
    payload = {
        "file": {
            "format": "JPEG",
            "width": 10,
            "height": 10,
            "size_bytes": 100,
            "sha256": "0" * 64,
        },
        "capture": {"camera": None, "captured_at": None},
        "metadata": {"exif": False, "xmp": False, "iptc": False, "software": None},
        "c2pa": {
            "present": False,
            "valid": None,
            "claim_generator": None,
            "generative_edit": False,
        },
        "assessment": {"type": "UNKNOWN", "confidence": "low", "reason": ["No evidence"]},
        "unexpected": True,
    }
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(payload)
