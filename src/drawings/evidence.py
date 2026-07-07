import re

from src.drawings.schemas import DrawingEvidenceFact, DrawingEvidenceResponse
from src.llm.gemini_llm import GeminiLlm


SETBACK_FACT_TERMS = ("setback", "side", "rear", "front", "boundary")
BUILDING_ELEMENT_TERMS = ("building", "wall", "external", "face", "addition")
BOUNDARY_ENDPOINT_TERMS = ("title boundary", "allotment boundary", "boundary")
SERVICE_TERMS = (
    "solatube",
    "vent",
    "chimney",
    "gutter",
    "downpipe",
    "dp-",
    "service",
    "roof",
    "skylight",
)
NON_BUILDING_DIMENSION_TERMS = (
    "courtyard",
    "internal garden",
    "study",
    "bedroom",
    "bathroom",
    "laundry",
    "joinery",
    "paving",
    "rear garden",
    "front garden",
)
REJECTED_PROXIMITY_CLASSIFICATIONS = (
    "internal_dimension",
    "open_space_or_courtyard_dimension",
    "service_or_roof_dimension",
)


DRAWING_EVIDENCE_PROMPT = """
You are inspecting architectural drawing images to extract only the visual evidence
needed to answer the user's question.

Use the attached drawing images as the source of truth. Use the page text and any
cached drawing facts only as helpers. If those helpers conflict with the image,
prefer the image and say what conflicted.

Return concise structured evidence. Do not assess planning compliance unless the
question only asks for drawing facts; compliance will be assessed in a later step.

For each relevant fact:
- identify the original_pdf_page and image_path from the image manifest
- identify the sheet number/title if visible
- distinguish existing, retained, demolished, and proposed work
- identify what a dimension measures: building wall, boundary, roof/eave/gutter,
  downpipe, vent/chimney/solatube, awning, service, fence, open space, etc.
- avoid treating service/roof/fixture dimensions as building wall dimensions
- include confidence and caveats for small/ambiguous drawing text

For building setback questions:
- A dimension is a building setback only if one endpoint clearly references a title
  boundary or allotment boundary and the other endpoint clearly references an
  external building wall or face.
- For every candidate building setback, populate endpoint_a, endpoint_b, and
  nearby_labels. endpoint_a and endpoint_b must name the two dimension endpoints,
  not just restate the dimension value.
- Do not classify courtyard dimensions, internal room dimensions, paving dimensions,
  joinery dimensions, service clearances, roof-service clearances, or gaps to an
  existing boundary wall as building setbacks.
- Do not classify a room as proposed or changed merely because it appears on a
  proposed plan. Use notes, clouded revision areas, linework, or labels to
  distinguish unchanged existing rooms from proposed additions.
- If the visual evidence shows a dimension but the endpoints are unclear, return it
  as an ambiguous_dimension fact, not as a setback fact.
- If a cached/OCR helper says a dimension is a setback but the image does not clearly
  support that, include a caveat explaining the conflict.
"""


def extract_visual_evidence(
    question: str,
    image_paths: list[str],
    drawing_context: str,
    llm: GeminiLlm | None = None,
) -> DrawingEvidenceResponse | None:
    if not image_paths:
        return None

    extractor = llm or GeminiLlm(schema=DrawingEvidenceResponse)
    prompt = build_visual_evidence_prompt(question, image_paths, drawing_context)
    evidence = extractor.get_response(prompt, image_paths=image_paths)
    return validate_visual_evidence(evidence, drawing_context)


def build_visual_evidence_prompt(
    question: str,
    image_paths: list[str],
    drawing_context: str,
) -> str:
    return "\n\n".join(
        [
            DRAWING_EVIDENCE_PROMPT,
            f"User question: {question}",
            build_image_manifest(image_paths),
            f"Drawing text/context helpers:\n{drawing_context}",
        ]
    )


def build_image_manifest(image_paths: list[str]) -> str:
    lines = [
        "Image manifest. Use these exact original_pdf_page and image_path values in the JSON response:"
    ]

    for image_path in image_paths:
        page_number = extract_page_number_from_image_path(image_path)
        lines.append(f"- original_pdf_page={page_number}; image_path={image_path}")

    return "\n".join(lines)


def extract_page_number_from_image_path(image_path: str) -> int | None:
    match = re.search(r"p(\d+)\.png$", image_path)
    if not match:
        return None

    return int(match.group(1))


def validate_visual_evidence(
    evidence: DrawingEvidenceResponse,
    drawing_context: str,
) -> DrawingEvidenceResponse:
    for fact in evidence.facts:
        validate_fact(fact, drawing_context)

    return evidence


def validate_fact(fact: DrawingEvidenceFact, drawing_context: str) -> None:
    if not is_candidate_building_setback(fact):
        fact.validation_status = "accepted"
        fact.validation_reason = "Not a candidate building setback dimension."
        return

    fact_text = normalise_text(
        " ".join(
            filter(
                None,
                [
                    fact.fact_type,
                    fact.finding,
                    fact.element,
                    fact.status,
                    fact.evidence,
                    fact.caveat,
                    fact.endpoint_a,
                    fact.endpoint_b,
                    " ".join(fact.nearby_labels),
                ],
            )
        )
    )
    endpoint_text = normalise_text(
        " ".join(filter(None, [fact.endpoint_a, fact.endpoint_b]))
    )
    value_windows = context_windows_for_fact_value(fact, drawing_context)
    proximity_classifications = proximity_classifications_for_fact_value(
        fact,
        drawing_context,
    )

    if contains_any(fact_text, SERVICE_TERMS):
        reject_fact(
            fact,
            "Rejected as a building setback because the evidence refers to a "
            "service, roof fixture, or roof element.",
        )
        return

    rejected_classification = first_rejected_proximity_classification(
        proximity_classifications
    )
    if rejected_classification:
        reject_fact(
            fact,
            "Rejected as a building setback because dimension proximity evidence "
            f"classifies the same value as {rejected_classification}.",
        )
        return

    if context_windows_contain_disqualifying_dimension(value_windows):
        reject_fact(
            fact,
            "Rejected as a building setback because the same dimension appears "
            "near courtyard/internal-room/open-space labels in the drawing text, "
            "not near a title-boundary-to-external-wall relationship.",
        )
        return

    if contains_any(fact_text, NON_BUILDING_DIMENSION_TERMS) and not has_endpoint_proof(
        endpoint_text
    ):
        ambiguous_fact(
            fact,
            "Downgraded because nearby labels indicate this may be an internal, "
            "courtyard, garden, or paving dimension rather than a building "
            "setback.",
        )
        return

    if not has_endpoint_proof(endpoint_text) and not has_endpoint_proof(fact_text):
        ambiguous_fact(
            fact,
            "Downgraded because the evidence does not identify one endpoint as "
            "a title/allotment boundary and the other as an external building "
            "wall or face.",
        )
        return

    fact.validation_status = "accepted"
    fact.validation_reason = (
        "Accepted as a candidate building setback because the evidence identifies "
        "a boundary endpoint and an external building wall/face endpoint."
    )


def is_candidate_building_setback(fact: DrawingEvidenceFact) -> bool:
    text = normalise_text(
        " ".join(filter(None, [fact.fact_type, fact.finding, fact.element]))
    )
    return contains_any(text, SETBACK_FACT_TERMS) and contains_any(
        text, BUILDING_ELEMENT_TERMS
    )


def context_windows_for_fact_value(
    fact: DrawingEvidenceFact,
    drawing_context: str,
    window_size: int = 180,
) -> list[str]:
    numbers = extract_numeric_values(fact.value)
    if not numbers:
        numbers = extract_numeric_values(fact.finding)

    lowered_context = normalise_text(drawing_context)
    windows = []

    for number in numbers:
        for match in re.finditer(rf"(?<!\d){re.escape(number)}(?!\d)", lowered_context):
            start = max(0, match.start() - window_size)
            end = min(len(lowered_context), match.end() + window_size)
            windows.append(lowered_context[start:end])

    return windows


def extract_numeric_values(value: str | None) -> list[str]:
    if not value:
        return []

    return re.findall(r"\d+(?:\.\d+)?", value)


def proximity_classifications_for_fact_value(
    fact: DrawingEvidenceFact,
    drawing_context: str,
) -> list[str]:
    numbers = extract_numeric_values(fact.value)
    if not numbers:
        numbers = extract_numeric_values(fact.finding)

    classifications = []
    for line in drawing_context.splitlines():
        normalised_line = normalise_text(line)
        if not normalised_line.startswith("page="):
            continue

        for number in numbers:
            if f"value={number}" not in normalised_line:
                continue

            match = re.search(r"classification=([a-z_]+)", normalised_line)
            if match:
                classifications.append(match.group(1))

    return classifications


def first_rejected_proximity_classification(
    classifications: list[str],
) -> str | None:
    for classification in classifications:
        if classification in REJECTED_PROXIMITY_CLASSIFICATIONS:
            return classification

    return None


def context_windows_contain_disqualifying_dimension(windows: list[str]) -> bool:
    for window in windows:
        if not contains_any(window, NON_BUILDING_DIMENSION_TERMS):
            continue

        if has_endpoint_proof(window):
            continue

        return True

    return False


def has_endpoint_proof(text: str) -> bool:
    return contains_any(text, BOUNDARY_ENDPOINT_TERMS) and contains_any(
        text, BUILDING_ELEMENT_TERMS
    )


def reject_fact(fact: DrawingEvidenceFact, reason: str) -> None:
    fact.validation_status = "rejected"
    fact.validation_reason = reason
    fact.confidence = "low"
    fact.fact_type = f"rejected_{fact.fact_type}"
    fact.caveat = append_validation_caveat(fact.caveat, reason)


def ambiguous_fact(fact: DrawingEvidenceFact, reason: str) -> None:
    fact.validation_status = "ambiguous"
    fact.validation_reason = reason
    fact.confidence = "low"
    if "ambiguous" not in fact.fact_type.lower():
        fact.fact_type = f"ambiguous_{fact.fact_type}"
    fact.caveat = append_validation_caveat(fact.caveat, reason)


def append_validation_caveat(existing: str | None, reason: str) -> str:
    if not existing:
        return reason

    return f"{existing} {reason}"


def contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def normalise_text(text: str) -> str:
    return " ".join(text.lower().split())


def format_visual_evidence_for_prompt(
    evidence: DrawingEvidenceResponse | None,
) -> str:
    if evidence is None:
        return "No query-specific visual drawing evidence extracted."

    lines = [
        "Query-specific visual drawing evidence:",
        f"question: {evidence.question}",
        f"relevant_pages: {evidence.relevant_pages}",
        f"summary: {evidence.summary}",
    ]

    for fact in evidence.facts:
        lines.append(
            " | ".join(
                [
                    f"original_pdf_page={fact.original_pdf_page}",
                    f"image_path={fact.image_path}",
                    f"sheet_number={fact.sheet_number}",
                    f"sheet_title={fact.sheet_title}",
                    f"fact_type={fact.fact_type}",
                    f"finding={fact.finding}",
                    f"value={fact.value}",
                    f"unit={fact.unit}",
                    f"element={fact.element}",
                    f"status={fact.status}",
                    f"evidence={fact.evidence}",
                    f"confidence={fact.confidence}",
                    f"caveat={fact.caveat}",
                    f"endpoint_a={fact.endpoint_a}",
                    f"endpoint_b={fact.endpoint_b}",
                    f"nearby_labels={fact.nearby_labels}",
                    f"validation_status={fact.validation_status}",
                    f"validation_reason={fact.validation_reason}",
                ]
            )
        )

    if evidence.caveats:
        lines.append("caveats:")
        lines.extend(f"- {caveat}" for caveat in evidence.caveats)

    return "\n".join(lines)
