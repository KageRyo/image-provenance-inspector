from app.models.result import C2PASummary, EditingType, OriginType
from app.provenance.rules import classify_provenance


def empty_c2pa() -> C2PASummary:
    return C2PASummary(
        present=False,
        valid=None,
        claim_generator=None,
        actions=[],
        generative_edit=False,
    )


def test_camera_metadata_is_medium_confidence_origin_evidence() -> None:
    assessment = classify_provenance(
        camera="ExampleCam Model 1",
        software=None,
        c2pa=empty_c2pa(),
    )

    assert assessment.origin.type is OriginType.CAMERA_CAPTURED
    assert assessment.origin.confidence.value == "medium"
    assert assessment.editing.type is EditingType.NONE_DETECTED


def test_camera_with_generative_c2pa_has_independent_evidence() -> None:
    assessment = classify_provenance(
        camera="ExampleCam Model 1",
        software="Adobe Photoshop",
        c2pa=C2PASummary(
            present=True,
            valid=True,
            claim_generator="Adobe Photoshop",
            actions=["generative edit"],
            generative_edit=True,
        ),
    )

    assert assessment.origin.type is OriginType.CAMERA_CAPTURED
    assert assessment.editing.type is EditingType.GENERATIVE
    assert assessment.editing.confidence.value == "high"


def test_known_generator_without_camera_is_synthetic_evidence() -> None:
    assessment = classify_provenance(
        camera=None,
        software="Stable Diffusion",
        c2pa=empty_c2pa(),
    )

    assert assessment.origin.type is OriginType.SYNTHETIC
    assert assessment.editing.type is EditingType.GENERATIVE


def test_generative_action_without_known_origin_stays_unknown() -> None:
    assessment = classify_provenance(
        camera=None,
        software=None,
        c2pa=C2PASummary(
            present=True,
            valid=True,
            claim_generator="Example Editor",
            actions=["generative edit"],
            generative_edit=True,
        ),
    )

    assert assessment.origin.type is OriginType.UNKNOWN
    assert assessment.editing.type is EditingType.GENERATIVE
