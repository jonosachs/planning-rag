import math
import re
from dataclasses import dataclass

import fitz


DIMENSION_VALUE_RE = re.compile(r"^\d{2,5}$")
MAX_PROXIMITY_DISTANCE = 220.0
MAX_PROXIMITY_CONTEXT_ITEMS = 40

BOUNDARY_LABEL_TERMS = (
    "boundary",
    "title",
    "allotment",
)
BUILDING_LABEL_TERMS = (
    "external",
    "wall",
    "building",
    "addition",
    "additions",
    "masonry",
    "parapet",
)
INTERNAL_LABEL_TERMS = (
    "courtyard",
    "study",
    "bedroom",
    "bathroom",
    "laundry",
    "joinery",
    "kitchen",
    "living",
    "dining",
    "garden",
    "paving",
)
SERVICE_LABEL_TERMS = (
    "solatube",
    "vent",
    "gutter",
    "downpipe",
    "roof",
    "chimney",
    "skylight",
    "service",
)


@dataclass(frozen=True)
class TextToken:
    page: int
    text: str
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class NearestLabel:
    text: str | None
    distance: float | None


@dataclass(frozen=True)
class DimensionProximity:
    page: int
    value: str
    bbox: tuple[float, float, float, float]
    classification: str
    reason: str
    nearest_boundary: NearestLabel
    nearest_building: NearestLabel
    nearest_internal: NearestLabel
    nearest_service: NearestLabel


def extract_dimension_proximity_evidence(
    pdf_path: str,
    image_paths: list[str],
) -> str:
    page_numbers = extract_page_numbers_from_image_paths(image_paths)
    if not page_numbers:
        return "No dimension proximity evidence."

    document = fitz.open(pdf_path)
    dimensions = []

    for page_number in page_numbers:
        page_index = page_number - 1
        if page_index < 0 or page_index >= len(document):
            continue

        dimensions.extend(analyse_page_dimension_proximity(document[page_index]))

    relevant_dimensions = sorted(
        [
            dimension
            for dimension in dimensions
            if is_relevant_dimension_proximity(dimension)
        ],
        key=dimension_relevance_key,
    )[:MAX_PROXIMITY_CONTEXT_ITEMS]

    if not relevant_dimensions:
        return "No dimension proximity evidence."

    lines = [
        "Dimension proximity evidence:",
        (
            "These classifications use PDF text bbox proximity only. They are "
            "supporting evidence, not geometric endpoint proof."
        ),
    ]
    lines.extend(format_dimension_proximity(dimension) for dimension in relevant_dimensions)
    return "\n".join(lines)


def extract_page_numbers_from_image_paths(image_paths: list[str]) -> list[int]:
    page_numbers = []

    for image_path in image_paths:
        match = re.search(r"p(\d+)\.png$", image_path)
        if not match:
            continue

        page_number = int(match.group(1))
        if page_number not in page_numbers:
            page_numbers.append(page_number)

    return page_numbers


def analyse_page_dimension_proximity(page) -> list[DimensionProximity]:
    page_number = page.number + 1
    tokens = extract_text_tokens(page)
    dimension_tokens = [token for token in tokens if is_dimension_token(token)]

    boundary_labels = filter_tokens(tokens, BOUNDARY_LABEL_TERMS)
    building_labels = filter_tokens(tokens, BUILDING_LABEL_TERMS)
    internal_labels = filter_tokens(tokens, INTERNAL_LABEL_TERMS)
    service_labels = filter_tokens(tokens, SERVICE_LABEL_TERMS)

    return [
        classify_dimension_token(
            token,
            boundary_labels=boundary_labels,
            building_labels=building_labels,
            internal_labels=internal_labels,
            service_labels=service_labels,
        )
        for token in dimension_tokens
    ]


def extract_text_tokens(page) -> list[TextToken]:
    tokens = []
    for word in page.get_text("words"):
        x0, y0, x1, y1, text = word[:5]
        cleaned = clean_token(text)
        if not cleaned:
            continue

        tokens.append(
            TextToken(
                page=page.number + 1,
                text=cleaned,
                bbox=(x0, y0, x1, y1),
            )
        )

    return tokens


def clean_token(text: str) -> str:
    return text.strip().lower().strip(".,;:()[]{}")


def is_dimension_token(token: TextToken) -> bool:
    if not DIMENSION_VALUE_RE.match(token.text):
        return False

    value = int(token.text)
    return 100 <= value <= 50000


def filter_tokens(tokens: list[TextToken], terms: tuple[str, ...]) -> list[TextToken]:
    return [token for token in tokens if token.text in terms]


def classify_dimension_token(
    token: TextToken,
    boundary_labels: list[TextToken],
    building_labels: list[TextToken],
    internal_labels: list[TextToken],
    service_labels: list[TextToken],
) -> DimensionProximity:
    nearest_boundary = nearest_label(token, boundary_labels)
    nearest_building = nearest_label(token, building_labels)
    nearest_internal = nearest_label(token, internal_labels)
    nearest_service = nearest_label(token, service_labels)

    classification, reason = classify_by_nearest_context(
        nearest_boundary,
        nearest_building,
        nearest_internal,
        nearest_service,
    )

    return DimensionProximity(
        page=token.page,
        value=token.text,
        bbox=token.bbox,
        classification=classification,
        reason=reason,
        nearest_boundary=nearest_boundary,
        nearest_building=nearest_building,
        nearest_internal=nearest_internal,
        nearest_service=nearest_service,
    )


def nearest_label(token: TextToken, labels: list[TextToken]) -> NearestLabel:
    if not labels:
        return NearestLabel(text=None, distance=None)

    nearest = min(labels, key=lambda label: bbox_distance(token.bbox, label.bbox))
    return NearestLabel(
        text=nearest.text,
        distance=round(bbox_distance(token.bbox, nearest.bbox), 1),
    )


def bbox_distance(
    bbox_a: tuple[float, float, float, float],
    bbox_b: tuple[float, float, float, float],
) -> float:
    ax, ay = bbox_center(bbox_a)
    bx, by = bbox_center(bbox_b)
    return math.dist((ax, ay), (bx, by))


def bbox_center(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    x0, y0, x1, y1 = bbox
    return ((x0 + x1) / 2, (y0 + y1) / 2)


def classify_by_nearest_context(
    nearest_boundary: NearestLabel,
    nearest_building: NearestLabel,
    nearest_internal: NearestLabel,
    nearest_service: NearestLabel,
) -> tuple[str, str]:
    if is_close(nearest_service) and closer_than(
        nearest_service,
        nearest_boundary,
        nearest_building,
        nearest_internal,
    ):
        return (
            "service_or_roof_dimension",
            "nearest contextual label is a service/roof term.",
        )

    if is_close(nearest_internal) and closer_than(
        nearest_internal,
        nearest_boundary,
        nearest_building,
    ):
        return (
            internal_dimension_classification(nearest_internal.text),
            "nearest contextual label is internal/open-space text, not a boundary.",
        )

    if is_close(nearest_boundary) and is_close(nearest_building):
        return (
            "possible_building_setback",
            "near both boundary text and building/wall/addition text.",
        )

    if is_close(nearest_boundary):
        return (
            "boundary_related_dimension",
            "near boundary text, but no nearby building/wall text was found.",
        )

    return (
        "ambiguous_dimension",
        "no close boundary, building, internal, or service label was found.",
    )


def internal_dimension_classification(label: str | None) -> str:
    if label in {"courtyard", "garden", "paving"}:
        return "open_space_or_courtyard_dimension"

    return "internal_dimension"


def is_close(label: NearestLabel) -> bool:
    return label.distance is not None and label.distance <= MAX_PROXIMITY_DISTANCE


def closer_than(candidate: NearestLabel, *others: NearestLabel) -> bool:
    if candidate.distance is None:
        return False

    return all(
        other.distance is None or candidate.distance < other.distance
        for other in others
    )


def is_relevant_dimension_proximity(dimension: DimensionProximity) -> bool:
    if dimension.classification in {
        "possible_building_setback",
        "boundary_related_dimension",
    }:
        return True

    if dimension.classification in {
        "internal_dimension",
        "open_space_or_courtyard_dimension",
        "service_or_roof_dimension",
    }:
        return nearest_context_distance(dimension) <= 100

    return False


def dimension_relevance_key(dimension: DimensionProximity) -> tuple[int, int, float]:
    priority_by_classification = {
        "possible_building_setback": 0,
        "boundary_related_dimension": 1,
        "open_space_or_courtyard_dimension": 2,
        "internal_dimension": 3,
        "service_or_roof_dimension": 4,
    }
    return (
        priority_by_classification.get(dimension.classification, 9),
        dimension.page,
        nearest_context_distance(dimension),
    )


def nearest_context_distance(dimension: DimensionProximity) -> float:
    distances = [
        label.distance
        for label in (
            dimension.nearest_boundary,
            dimension.nearest_building,
            dimension.nearest_internal,
            dimension.nearest_service,
        )
        if label.distance is not None
    ]
    if not distances:
        return float("inf")

    return min(distances)


def format_dimension_proximity(dimension: DimensionProximity) -> str:
    return " | ".join(
        [
            f"page={dimension.page}",
            f"value={dimension.value}",
            f"bbox={tuple(round(value, 1) for value in dimension.bbox)}",
            f"classification={dimension.classification}",
            f"reason={dimension.reason}",
            f"nearest_boundary={format_nearest_label(dimension.nearest_boundary)}",
            f"nearest_building={format_nearest_label(dimension.nearest_building)}",
            f"nearest_internal={format_nearest_label(dimension.nearest_internal)}",
            f"nearest_service={format_nearest_label(dimension.nearest_service)}",
        ]
    )


def format_nearest_label(label: NearestLabel) -> str:
    if label.text is None or label.distance is None:
        return "none"

    return f"{label.text}@{label.distance}"
