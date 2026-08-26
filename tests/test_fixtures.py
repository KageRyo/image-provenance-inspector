from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from app.service import AnalysisService

REPOSITORY_ROOT = Path(__file__).parents[1]
MANIFEST_PATH = REPOSITORY_ROOT / "fixtures" / "manifest.json"


def _fixture_entries() -> list[dict[str, Any]]:
    payload = json.loads(MANIFEST_PATH.read_text())
    assert payload["schema_version"] == 2
    return payload["fixtures"]


def test_fixture_manifest_has_traceable_assets() -> None:
    entries = _fixture_entries()

    assert entries
    for entry in entries:
        asset_path = (REPOSITORY_ROOT / entry["path"]).resolve()
        source = entry["source"]
        workflow = entry["workflow"]
        expected = entry["expected"]
        assert asset_path.is_relative_to(REPOSITORY_ROOT)
        assert asset_path.is_file()
        assert source["url"].startswith("https://")
        assert len(source["commit"]) == 40
        assert source["license"]
        assert len(source["sha256"]) == 64
        assert workflow["tool"]
        assert workflow["tool_version"]
        assert workflow["description"]
        assert expected["exif_preserved"] in {True, False, None}
        assert hashlib.sha256(asset_path.read_bytes()).hexdigest() == source["sha256"]


@pytest.mark.parametrize("fixture", _fixture_entries(), ids=lambda item: item["id"])
def test_real_fixture_matches_evidence_expectations(fixture: dict[str, Any]) -> None:
    asset_path = REPOSITORY_ROOT / fixture["path"]
    result = AnalysisService().analyze(asset_path.read_bytes())
    expected = fixture["expected"]

    assert result.c2pa.present is expected["c2pa_present"]
    assert set(expected["actions"]).issubset(result.c2pa.actions)
    assert result.metadata.exif is expected["exif_present"]
    assert result.assessment.origin.type.value == expected["origin"]
    assert result.assessment.editing.type.value == expected["editing"]
