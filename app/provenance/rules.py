"""Conservative, explainable provenance evidence classification rules."""

from __future__ import annotations

from collections.abc import Iterable

from ..models.result import (
    Assessment,
    C2PASummary,
    Confidence,
    EditingAssessment,
    EditingType,
    OriginAssessment,
    OriginType,
)

_AI_EDIT_MARKERS = (
    "artificial intelligence",
    "ai-generated",
    "ai generated",
    "generative",
    "firefly",
    "gemini",
    "sora",
)
_AI_GENERATOR_MARKERS = (
    "midjourney",
    "stable diffusion",
    "dall-e",
    "dall·e",
    "chatgpt image",
    "imagen",
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
_EDIT_ACTION_MARKERS = (
    "edited",
    "edit",
    "placed",
    "removed",
    "exported",
)
_CREATED_ACTION_MARKERS = ("created", "generated")


def _contains_marker(value: str | None, markers: Iterable[str]) -> bool:
    normalized = (value or "").casefold()
    return any(marker in normalized for marker in markers)


def _contains_action(actions: list[str], markers: Iterable[str]) -> bool:
    return any(_contains_marker(action, markers) for action in actions)


def _camera_origin(camera: str | None) -> OriginAssessment:
    if camera:
        return OriginAssessment(
            type=OriginType.CAMERA_CAPTURED,
            confidence=Confidence.MEDIUM,
            reason=[
                "Camera capture metadata detected",
                "Metadata can be copied, rewritten, or retained after editing",
            ],
        )
    return OriginAssessment(
        type=OriginType.UNKNOWN,
        confidence=Confidence.LOW,
        reason=[
            "No camera-origin metadata was detected",
            "Missing metadata is not proof that an image is synthetic",
        ],
    )


def _origin_assessment(
    *, camera: str | None, software: str | None, c2pa: C2PASummary
) -> OriginAssessment:
    if camera:
        return _camera_origin(camera)

    generator_evidence = _contains_marker(software, _AI_GENERATOR_MARKERS) or _contains_marker(
        c2pa.claim_generator, _AI_GENERATOR_MARKERS
    )
    created_evidence = _contains_action(c2pa.actions, _CREATED_ACTION_MARKERS)
    if generator_evidence and (not c2pa.present or created_evidence or c2pa.generative_edit):
        return OriginAssessment(
            type=OriginType.SYNTHETIC,
            confidence=Confidence.MEDIUM,
            reason=[
                "Known AI generator evidence detected",
                "No camera-origin metadata was detected",
                "Source history may be incomplete",
            ],
        )

    if c2pa.generative_edit:
        return OriginAssessment(
            type=OriginType.UNKNOWN,
            confidence=Confidence.MEDIUM,
            reason=[
                "Generative action detected",
                "No camera-origin metadata was detected",
                "The available evidence cannot distinguish generated content from an edited source",
            ],
        )
    return _camera_origin(None)


def _editing_assessment(*, software: str | None, c2pa: C2PASummary) -> EditingAssessment:
    ai_evidence = (
        c2pa.generative_edit
        or _contains_marker(software, _AI_EDIT_MARKERS)
        or _contains_marker(c2pa.claim_generator, _AI_EDIT_MARKERS)
        or _contains_marker(software, _AI_GENERATOR_MARKERS)
        or _contains_marker(c2pa.claim_generator, _AI_GENERATOR_MARKERS)
    )
    if ai_evidence:
        return EditingAssessment(
            type=EditingType.GENERATIVE,
            confidence=Confidence.HIGH if c2pa.generative_edit else Confidence.MEDIUM,
            reason=[
                "Generative editing or AI provenance evidence detected",
                *(["C2PA generative action detected"] if c2pa.generative_edit else []),
            ],
        )

    traditional_evidence = _contains_marker(software, _TRADITIONAL_EDIT_MARKERS)
    action_evidence = _contains_action(c2pa.actions, _EDIT_ACTION_MARKERS)
    if traditional_evidence or action_evidence:
        reasons = []
        if traditional_evidence:
            reasons.append("Traditional image-editing software detected")
        if action_evidence:
            reasons.append("Non-generative edit action detected in provenance")
        return EditingAssessment(
            type=EditingType.TRADITIONAL,
            confidence=Confidence.HIGH if traditional_evidence else Confidence.MEDIUM,
            reason=reasons,
        )

    if c2pa.present:
        return EditingAssessment(
            type=EditingType.UNKNOWN,
            confidence=Confidence.LOW,
            reason=[
                "C2PA provenance detected",
                "No editing action was available to classify",
            ],
        )
    return EditingAssessment(
        type=EditingType.NONE_DETECTED,
        confidence=Confidence.LOW,
        reason=[
            "No editing provenance was detected",
            "Missing evidence is not proof that an image was not edited",
        ],
    )


def classify_provenance(
    *,
    camera: str | None,
    software: str | None,
    c2pa: C2PASummary,
) -> Assessment:
    """Classify origin and editing evidence independently.

    Camera metadata is treated as medium-confidence origin evidence rather than
    proof of an untouched image. Generative actions without a known generator
    remain origin-unknown because a real source image may have lost its metadata.
    """

    return Assessment(
        origin=_origin_assessment(camera=camera, software=software, c2pa=c2pa),
        editing=_editing_assessment(software=software, c2pa=c2pa),
    )
