from src.drawings.evidence import validate_visual_evidence
from src.drawings.schemas import DrawingEvidenceFact, DrawingEvidenceResponse


def make_response(fact: DrawingEvidenceFact) -> DrawingEvidenceResponse:
    return DrawingEvidenceResponse(
        question="do the building setbacks comply?",
        relevant_pages=[4],
        facts=[fact],
        summary="candidate facts",
    )


def make_setback_fact(
    value: str,
    evidence: str,
    endpoint_a: str | None = "title boundary",
    endpoint_b: str | None = "external building wall",
) -> DrawingEvidenceFact:
    return DrawingEvidenceFact(
        original_pdf_page=4,
        image_path="tmp/p4.png",
        fact_type="setback",
        finding=f"Candidate building setback is {value}mm.",
        value=value,
        unit="mm",
        element="building wall",
        status="proposed",
        evidence=evidence,
        confidence="high",
        endpoint_a=endpoint_a,
        endpoint_b=endpoint_b,
    )


def test_validate_visual_evidence_rejects_study_dimension_as_building_setback():
    evidence = make_response(
        make_setback_fact(
            "980",
            "The model described 980 as a north side setback.",
        )
    )
    drawing_context = (
        "Selected drawing page 4 full PDF text: STUDY W05 980 440 "
        "joinery A6.02 existing wall."
    )

    validated = validate_visual_evidence(evidence, drawing_context)

    fact = validated.facts[0]
    assert fact.validation_status == "rejected"
    assert fact.fact_type == "rejected_setback"
    assert "courtyard/internal-room" in fact.validation_reason


def test_validate_visual_evidence_rejects_courtyard_dimension_as_building_setback():
    evidence = make_response(
        make_setback_fact(
            "2825",
            "The model described 2825 as a rear building setback.",
        )
    )
    drawing_context = (
        "Selected drawing page 3 full PDF text: COURTYARD refer to drawing 04 "
        "below 2825 paving internal garden removed."
    )

    validated = validate_visual_evidence(evidence, drawing_context)

    assert validated.facts[0].validation_status == "rejected"


def test_validate_visual_evidence_rejects_proximity_classified_internal_dimension():
    evidence = make_response(
        make_setback_fact(
            "980",
            "The model described 980 as a north side setback.",
        )
    )
    drawing_context = (
        "Dimension proximity evidence:\n"
        "page=4 | value=980 | classification=internal_dimension | "
        "reason=nearest contextual label is internal/open-space text"
    )

    validated = validate_visual_evidence(evidence, drawing_context)

    fact = validated.facts[0]
    assert fact.validation_status == "rejected"
    assert "internal_dimension" in fact.validation_reason


def test_validate_visual_evidence_accepts_boundary_to_external_wall_dimension():
    evidence = make_response(
        make_setback_fact(
            "1030",
            "1030 is shown from title boundary to the external wall of the addition.",
        )
    )
    drawing_context = (
        "Selected drawing page 4 full PDF text: title boundary 234 43 39.62 "
        "1030 external building wall living addition."
    )

    validated = validate_visual_evidence(evidence, drawing_context)

    fact = validated.facts[0]
    assert fact.validation_status == "accepted"
    assert "boundary endpoint" in fact.validation_reason


def test_validate_visual_evidence_downgrades_missing_endpoint_proof():
    evidence = make_response(
        make_setback_fact(
            "350",
            "350 is visible near a wall.",
            endpoint_a=None,
            endpoint_b=None,
        )
    )
    drawing_context = "Selected drawing page 3 full PDF text: 350 existing fence."

    validated = validate_visual_evidence(evidence, drawing_context)

    assert validated.facts[0].validation_status == "ambiguous"
