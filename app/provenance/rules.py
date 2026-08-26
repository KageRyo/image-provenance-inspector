"""Conservative, explainable provenance classification rules."""

from __future__ import annotations

from collections.abc import Iterable

from ..models.result import Assessment, C2PASummary, Confidence, ProvenanceType

_AI_MARKERS = (
    "artificial intelligence",
    "ai-generated",
    "ai generated",
    "generative",
    "firefly",
    "midjourney",
    "stable diffusion",
    "dall-e",
    "dall·e",
    "gemini",
    "sora",
    "flux",
    "comfyui",
    "automatic1111",
)
_TRADITIONAL_EDIT_MARKERS = (
    "adobe photoshop",
    "photoshop",
    "lightroom",
    "capture one",
    "affinity photo",
    "gimp",
    "darktable",
    "pixelmator",
)


def _contains_marker(value: str | None, markers: Iterable[str]) -> bool:
    normalized = (value or "").casefold()
    return any(marker in normalized for marker in markers)


def classify_provenance(
    *,
    camera: str | None,
    software: str | None,
    c2pa: C2PASummary,
) -> Assessment:
    """Classify evidence without claiming certainty beyond the available data."""

    camera_detected = bool(camera)
    c2pa_generator = c2pa.claim_generator
    ai_software = _contains_marker(software, _AI_MARKERS) or _contains_marker(
        c2pa_generator, _AI_MARKERS
    )
    traditional_software = _contains_marker(software, _TRADITIONAL_EDIT_MARKERS)
    generative_evidence = c2pa.generative_edit or ai_software

    if generative_evidence and camera_detected:
        reasons = [
            "Camera capture metadata detected",
            "AI-related editing or generation evidence detected",
        ]
        if c2pa.present:
            reasons.insert(1, "C2PA provenance detected")
        if c2pa.generative_edit:
            reasons.append("Generative editing action detected")
        return Assessment(
            type=ProvenanceType.AI_ASSISTED_EDIT,
            confidence=Confidence.HIGH if c2pa.generative_edit else Confidence.MEDIUM,
            reason=reasons,
        )

    if generative_evidence and not camera_detected:
        reasons = ["AI-related generation evidence detected"]
        if c2pa.present:
            reasons.insert(0, "C2PA provenance detected")
        if c2pa.generative_edit:
            reasons.append("Generative action detected without camera-origin evidence")
        return Assessment(
            type=ProvenanceType.AI_GENERATED,
            confidence=Confidence.HIGH if c2pa.generative_edit else Confidence.MEDIUM,
            reason=reasons,
        )

    if camera_detected and (traditional_software or c2pa.present):
        reasons = ["Camera capture metadata detected"]
        if traditional_software:
            reasons.append("Traditional image-editing software detected")
        if c2pa.present:
            reasons.append("C2PA provenance detected without a generative action")
        return Assessment(
            type=ProvenanceType.TRADITIONAL_EDIT,
            confidence=Confidence.HIGH if traditional_software else Confidence.MEDIUM,
            reason=reasons,
        )

    if camera_detected:
        return Assessment(
            type=ProvenanceType.CAMERA_ORIGINAL,
            confidence=Confidence.HIGH,
            reason=[
                "Camera capture metadata detected",
                "No AI or editing provenance was detected",
            ],
        )

    return Assessment(
        type=ProvenanceType.UNKNOWN,
        confidence=Confidence.LOW,
        reason=[
            "No camera-origin metadata was detected",
            "No conclusive editing or generation provenance was detected",
        ],
    )
