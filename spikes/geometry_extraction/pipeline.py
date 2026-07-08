"""End-to-end setback pipeline: query -> pick drawing -> extract setbacks.

Wires the flow the integration test drives:
  1. list the sub-drawings on the sheet and label their viewports,
  2. the model picks the drawing(s) relevant to the query,
  3. the slice-21 routine runs on that viewport: per-boundary strip crop ->
     dimension pool -> focused LLM read -> cross-check -> governing setback.

The slice-21 helpers are imported, not duplicated.
"""

from dataclasses import dataclass, field

import numpy as np
import fitz

from spikes.geometry_extraction.envelope import envelope_mask
from spikes.geometry_extraction.geometry import clip_geometry, extract_page_geometry
from spikes.geometry_extraction.viewports import (
    extract_viewports,
    label_viewports,
    locate_titles,
)
from spikes.geometry_extraction.vision import (
    assess_boundary_strip,
    identify_front_boundary,
    list_titles,
    render_sheet,
    select_drawings,
)

OPPOSITE = {"top": "bottom", "bottom": "top", "left": "right", "right": "left"}
from spikes.geometry_extraction.run_slice21 import (
    MM_PER_PT,
    ON_FRACTION,
    ZOOM,
    boundary_edges_from_geometry,
    certify_offsets,
    edge_label,
    ensure_envelope,
    governing_offset,
    ignored_pool,
    is_dimension_text,
    render_strip,
    strip_rect,
    touch_fraction,
)

SHEET_PATH = "tmp/pipeline_sheet.png"
INPUT_PATH = "tmp/pipeline_in.png"
COLOURED_PATH = "tmp/pipeline_col.png"
MIN_EDGE_MM = 3000


@dataclass
class BoundarySetback:
    side: str
    role: str
    on_boundary: bool
    governing_mm: int | None
    governing_reason: str
    certified: list[tuple[int, str]] = field(default_factory=list)  # (value, status)
    ignored: list[int] = field(default_factory=list)
    model_envelope_disagree: bool = False


@dataclass
class SetbackAnswer:
    query: str
    drawing: str | None
    drawing_reason: str
    boundaries: list[BoundarySetback]
    front_side: str | None = None
    street_cue: str = ""
    front_confidence: str = ""


def answer_setbacks(pdf_path: str, query: str, page_number: int = 0) -> SetbackAnswer:
    page = fitz.open(pdf_path)[page_number]

    render_sheet(page, SHEET_PATH, max_width=4000)
    titles = list_titles(SHEET_PATH)
    labelled = label_viewports(extract_viewports(page), locate_titles(page, titles))

    choice = select_drawings(query, titles)
    rect = viewport_for(labelled, choice.titles)
    if rect is None:
        return SetbackAnswer(query, None, choice.reason, [])

    boundaries, front = extract_setbacks(pdf_path, page, page_number, rect)
    drawing = choice.titles[0] if choice.titles else None
    return SetbackAnswer(query, drawing, choice.reason, boundaries,
                         front_side=front.front_side, street_cue=front.street_cue,
                         front_confidence=front.confidence)


def extract_setbacks(pdf_path, page, page_number, rect):
    site_geo = clip_geometry(extract_page_geometry(page), rect)
    tokens = [t for t in site_geo.text_tokens if is_dimension_text(t.text)]

    wpx, hpx = ensure_envelope(pdf_path, page_number, rect, COLOURED_PATH, INPUT_PATH, ZOOM)
    mask = envelope_mask(COLOURED_PATH, (wpx, hpx))
    front = identify_front_boundary(INPUT_PATH)  # whole-plan: which edge is the street
    edges = boundary_edges_from_geometry(site_geo, rect)
    pts = [p for edge in edges for p in edge]
    cx, cy = np.mean([p[0] for p in pts]), np.mean([p[1] for p in pts])

    def in_mask(x, y):
        px, py = int((x - rect.x0) / rect.width * wpx), int((y - rect.y0) / rect.height * hpx)
        return 0 <= px < wpx and 0 <= py < hpx and bool(mask[py, px])

    results = []
    for i, (a, b) in enumerate(edges):
        if np.hypot(b[0] - a[0], b[1] - a[1]) * MM_PER_PT < MIN_EDGE_MM:
            continue
        side = edge_label(a, b, cx, cy)
        strip = strip_rect(a, b, cx, cy, rect)
        strip_path = f"tmp/pipeline_{i:02d}_{side}.png"
        render_strip(page, strip, strip_path)

        pool = [t for t in tokens if strip.contains(fitz.Point(t.center))]
        result = assess_boundary_strip(strip_path, side, [int(t.text.strip()) for t in pool])
        certified, dropped = certify_offsets(result.offsets, pool, strip)
        ignored = ignored_pool(pool, certified, dropped)
        on = touch_fraction(a, b, cx, cy, in_mask) >= ON_FRACTION
        gov_value, gov_reason = governing_offset(certified)

        results.append(BoundarySetback(
            side=side,
            role=role_for_side(side, front.front_side),
            on_boundary=on,
            governing_mm=0 if on else gov_value,
            governing_reason="on boundary" if on else gov_reason,
            certified=[(c.offset.value_mm, c.offset.status) for c in certified],
            ignored=[int(t.text.strip()) for t in ignored],
            model_envelope_disagree=result.building_on_boundary != on,
        ))
    return results, front


def role_for_side(side: str, front_side: str) -> str:
    if side == front_side:
        return "front"
    if side == OPPOSITE.get(front_side):
        return "rear"
    return "side"


def viewport_for(labelled, selected_titles: list[str]) -> fitz.Rect | None:
    wanted = [t.lower() for t in selected_titles]
    for vp in labelled:
        if vp.title and any(w in vp.title.lower() or vp.title.lower() in w for w in wanted):
            return fitz.Rect(vp.x0, vp.y0, vp.x1, vp.y1)
    return None
