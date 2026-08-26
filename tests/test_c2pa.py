from __future__ import annotations

import json

from app.analyzers import c2pa


class FakeReader:
    def __init__(self, _mime_type: str, _stream) -> None:
        pass

    def __enter__(self) -> FakeReader:
        return self

    def __exit__(self, *_args) -> None:
        return None

    def json(self) -> str:
        return json.dumps(
            {
                "active_manifest": "urn:example",
                "manifests": {
                    "urn:example": {
                        "claim_generator": "Example Editor",
                        "assertions": [
                            {
                                "label": "c2pa.actions.v2",
                                "data": {"actions": [{"action": "generative edit"}]},
                            }
                        ],
                    }
                },
            }
        )

    def get_validation_state(self) -> str:
        return "Valid"


def test_c2pa_reader_maps_manifest_and_actions(monkeypatch) -> None:
    monkeypatch.setattr(c2pa, "Reader", FakeReader)

    result = c2pa.inspect_c2pa(b"bytes", "image/jpeg")

    assert result.present is True
    assert result.valid is True
    assert result.claim_generator == "Example Editor"
    assert result.actions == ["generative edit"]
    assert result.generative_edit is True
