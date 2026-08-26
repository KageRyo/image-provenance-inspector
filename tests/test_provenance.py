from app.models.result import C2PASummary, ProvenanceType
from app.provenance.rules import classify_provenance


def test_camera_without_editing_evidence_is_camera_original() -> None:
    assessment = classify_provenance(
        camera="ExampleCam Model 1",
        software=None,
        c2pa=C2PASummary(present=False, valid=None, claim_generator=None, generative_edit=False),
    )
    assert assessment.type is ProvenanceType.CAMERA_ORIGINAL


def test_camera_with_generative_c2pa_is_ai_assisted_edit() -> None:
    assessment = classify_provenance(
        camera="ExampleCam Model 1",
        software="Adobe Photoshop",
        c2pa=C2PASummary(
            present=True,
            valid=True,
            claim_generator="Adobe Photoshop",
            generative_edit=True,
        ),
    )
    assert assessment.type is ProvenanceType.AI_ASSISTED_EDIT
    assert assessment.confidence.value == "high"


def test_ai_generator_without_camera_is_ai_generated() -> None:
    assessment = classify_provenance(
        camera=None,
        software="Stable Diffusion",
        c2pa=C2PASummary(present=False, valid=None, claim_generator=None, generative_edit=False),
    )
    assert assessment.type is ProvenanceType.AI_GENERATED
