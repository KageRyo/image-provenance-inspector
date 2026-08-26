"""Read C2PA Content Credentials when the native Python binding is available."""

from __future__ import annotations

import json
import logging
from io import BytesIO
from typing import Any

from ..models.result import C2PASummary

logger = logging.getLogger(__name__)

try:  # c2pa-python ships the ``c2pa`` import package.
    from c2pa import Reader
except ImportError:  # pragma: no cover - exercised in minimal installations
    Reader = None  # type: ignore[assignment,misc]


_GENERATION_MARKERS = (
    "generative",
    "generative-fill",
    "generative fill",
    "generative edit",
    "text-to-image",
    "text to image",
    "inpaint",
    "outpaint",
    "ai-generated",
    "ai generated",
    "synthetic",
)


def _validation_to_bool(state: Any) -> bool | None:
    if state is None:
        return None
    text = str(state).lower()
    if "invalid" in text or "error" in text or "fail" in text:
        return False
    if "valid" in text or "trusted" in text or "success" in text:
        return True
    return None


def _actions_from_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for assertion in manifest.get("assertions", []):
        if not isinstance(assertion, dict):
            continue
        label = str(assertion.get("label", ""))
        if label not in {"c2pa.actions", "c2pa.actions.v2"}:
            continue
        data = assertion.get("data", {})
        if isinstance(data, dict) and isinstance(data.get("actions"), list):
            actions.extend(action for action in data["actions"] if isinstance(action, dict))
    return actions


def _has_generative_evidence(manifest: dict[str, Any], claim_generator: str | None) -> bool:
    evidence = json.dumps(
        {"actions": _actions_from_manifest(manifest), "claim_generator": claim_generator},
        ensure_ascii=False,
    ).lower()
    return any(marker in evidence for marker in _GENERATION_MARKERS)


def inspect_c2pa(data: bytes, mime_type: str) -> C2PASummary:
    """Return a safe summary; absent/unsupported credentials are not fatal."""

    if Reader is None:
        return C2PASummary(present=False, valid=None, claim_generator=None, generative_edit=False)

    try:
        with Reader(mime_type, BytesIO(data)) as reader:
            manifest_store = json.loads(reader.json())
            active_label = manifest_store.get("active_manifest")
            manifests = manifest_store.get("manifests", {})
            manifest = manifests.get(active_label) if isinstance(manifests, dict) else None
            if not isinstance(manifest, dict):
                return C2PASummary(
                    present=False, valid=None, claim_generator=None, generative_edit=False
                )
            claim_generator_value = manifest.get("claim_generator")
            claim_generator = (
                str(claim_generator_value).strip() if claim_generator_value is not None else None
            )
            claim_generator = claim_generator or None
            return C2PASummary(
                present=True,
                valid=_validation_to_bool(reader.get_validation_state()),
                claim_generator=claim_generator,
                generative_edit=_has_generative_evidence(manifest, claim_generator),
            )
    except Exception as exc:  # native bindings expose several exception classes by version
        logger.debug("Unable to read C2PA manifest: %s", exc)
        return C2PASummary(present=False, valid=None, claim_generator=None, generative_edit=False)
