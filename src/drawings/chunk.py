from src.drawings.schemas import PageFeautres, PdfTextFeature
from src.indexing.schemas import Chunk


FEATURE_KEYWORDS = {
    "site_statistics": ("site statistics",),
    "site_area": ("site area",),
    "permeability": ("permeability",),
    "private_open_space": (
        "private open space",
        "secluded private open space",
        "s.p.o.s",
        "p.o.s",
    ),
    "setback": ("setback",),
    "overshadowing": ("overshadow", "shadow"),
    "height": ("building height", "roof height", "ceiling height", "height", "rl.", "rf."),
    "site_coverage": ("site coverage", "coverage"),
    "boundary": ("title boundary", "boundary"),
    "easement": ("easement",),
    "gross_floor_area": ("g.f.a",),
}


def batch_chunk(page_features: list[PageFeautres]) -> list[Chunk]:
    chunks = []

    for page in page_features:
        chunks.extend(chunk_page_features(page))

    return chunks


def chunk_page_features(page: PageFeautres) -> list[Chunk]:
    if not page.text_features:
        return []

    chunks = []

    for chunk_index, feature in enumerate(page.text_features):
        nearby_features = find_nearby_features(feature, page.text_features)
        text = build_feature_text(page.page, feature, nearby_features)
        chunks.append(
            Chunk(
                text=text,
                metadata=build_feature_metadata(page, feature, chunk_index),
            )
        )

    chunks.append(build_page_summary_chunk(page, len(chunks)))

    return chunks


def find_nearby_features(
    target: PdfTextFeature,
    features: list[PdfTextFeature],
    max_distance: float = 120,
) -> list[PdfTextFeature]:
    nearby = []
    target_centre = bbox_centre(target.bbox)

    for feature in features:
        if feature == target:
            continue

        feature_centre = bbox_centre(feature.bbox)
        if abs(feature_centre[1] - target_centre[1]) <= max_distance:
            nearby.append(feature)

    return nearby[:4]


def build_feature_text(
    page_number: int,
    feature: PdfTextFeature,
    nearby_features: list[PdfTextFeature],
) -> str:
    feature_type = classify_feature_type(feature.text)
    text = (
        f"Drawing page {page_number}. "
        f"Feature type: {feature_type}. "
        f"Source text: {feature.text}."
    )

    if nearby_features:
        nearby_text = "; ".join(feature.text for feature in nearby_features)
        text = f"{text} Nearby drawing text: {nearby_text}."

    return text


def build_page_summary_chunk(page: PageFeautres, chunk_index: int) -> Chunk:
    feature_text = "; ".join(feature.text for feature in page.text_features)
    text = (
        f"Drawing page {page.page} summary. "
        f"Planning-relevant drawing text: {feature_text}."
    )

    return Chunk(
        text=text,
        metadata={
            "source": "drawings",
            "chunk_kind": "page_summary",
            "page": page.page,
            "img_path": page.img_path,
            "feature_type": "page_summary",
            "chunk_index": chunk_index,
        },
    )


def build_feature_metadata(
    page: PageFeautres,
    feature: PdfTextFeature,
    chunk_index: int,
) -> dict:
    x0, y0, x1, y1 = feature.bbox

    return {
        "source": "drawings",
        "chunk_kind": "feature",
        "page": feature.page,
        "img_path": page.img_path,
        "feature_type": classify_feature_type(feature.text),
        "source_text": feature.text,
        "bbox_x0": x0,
        "bbox_y0": y0,
        "bbox_x1": x1,
        "bbox_y1": y1,
        "block_no": feature.block_no,
        "block_type": feature.block_type,
        "chunk_index": chunk_index,
    }


def classify_feature_type(text: str) -> str:
    lowered = text.lower()

    for feature_type, keywords in FEATURE_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return feature_type

    return "planning_annotation"


def bbox_centre(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    x0, y0, x1, y1 = bbox
    return ((x0 + x1) / 2, (y0 + y1) / 2)
