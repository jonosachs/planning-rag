"""Slice 21: per-boundary strips - crop, extract pool, LLM reads, cross-check.

For each boundary edge: crop a strip along it (extended inward by half the plan),
extract the numbered dimensions in that strip (the certified pool), have the LLM
read just that strip for setbacks, then cross-check its offsets against the pool:
  - LLM offset not in pool -> hallucination, drop
  - pool dim the LLM ignored -> flagged (running/chain or missed)
Envelope gives the authoritative on-boundary. Governing = 0 if on-boundary, else
the minimum certified offset.

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_slice21
"""

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import fitz

from spikes.geometry_extraction.envelope import envelope_mask, fill_building_envelope
from spikes.geometry_extraction.geometry import clip_geometry, extract_page_geometry
from spikes.geometry_extraction.schemas import OffsetDim, PageGeometry, TextToken
from spikes.geometry_extraction.viewports import (
    extract_viewports,
    label_viewports,
    locate_titles,
)
from spikes.geometry_extraction.vision import (
    assess_boundary_strip,
    list_titles,
    render_sheet,
)

SAMPLE_PDF = "assets/site_plan.pdf"
INPUT_PATH = "tmp/slice21_in.png"
COLOURED_PATH = "tmp/slice21_col.png"
ZOOM = 3.0
MM_PER_PT = 25.4 / 72 * 100
CROP_DEPTH_FRACTION = 0.5
TOKEN_NEAR_PT, TOUCH_MM, ON_FRACTION = 220, 500, 0.15
MAX_STRIP_WIDTH_PX = 2200
MAX_STRIP_HEIGHT_PX = 1400


@dataclass(frozen=True)
class CertifiedOffset:
    offset: OffsetDim
    token: TextToken
    distance_pt: float
    note: str


def main() -> None:
    page = fitz.open(SAMPLE_PDF)[0]
    rect = isolate_site_plan(page)
    site_geo = clip_geometry(extract_page_geometry(page), rect)
    tokens = [t for t in site_geo.text_tokens if is_dimension_text(t.text)]
    print(f"site-plan viewport: ({rect.x0:.0f},{rect.y0:.0f})-({rect.x1:.0f},{rect.y1:.0f})")
    print(f"dimension-like text tokens in viewport: {len(tokens)}", flush=True)

    wpx, hpx = ensure_envelope(SAMPLE_PDF, 0, rect, COLOURED_PATH, INPUT_PATH, ZOOM)
    mask = envelope_mask(COLOURED_PATH, (wpx, hpx))
    edges = boundary_edges_from_geometry(site_geo, rect)
    edge_points = [p for edge in edges for p in edge]
    cx, cy = np.mean([p[0] for p in edge_points]), np.mean([p[1] for p in edge_points])

    def in_mask(x, y):
        px, py = int((x - rect.x0) / rect.width * wpx), int((y - rect.y0) / rect.height * hpx)
        return 0 <= px < wpx and 0 <= py < hpx and bool(mask[py, px])

    print(f"deterministic boundary edges: {len(edges)}")
    print(f"crop depth fraction: {CROP_DEPTH_FRACTION:.2f} of plan extent")
    print("per-boundary (strip crop -> pool -> LLM -> cross-check):\n")
    for i, (a, b) in enumerate(edges):
        if math.dist(a, b) * MM_PER_PT < 3000:
            continue
        side = edge_label(a, b, cx, cy)
        strip = strip_rect(a, b, cx, cy, rect)
        strip_path = f"tmp/s21_{i:02d}_{side}.png"
        render_strip(page, strip, strip_path)

        pool = [t for t in tokens if strip.contains(fitz.Point(t.center))]
        candidate_values = [int(t.text.strip()) for t in pool]
        print(f"  {side}: crop={strip_path} pool={sorted(set(candidate_values))}", flush=True)

        result = assess_boundary_strip(strip_path, side, candidate_values)
        certified, dropped = certify_offsets(result.offsets, pool, strip)
        ignored = ignored_pool(pool, certified, dropped)
        on_fraction = touch_fraction(a, b, cx, cy, in_mask)
        on = on_fraction >= ON_FRACTION
        disagree = " [model/envelope disagree]" if result.building_on_boundary != on else ""

        gov_value, gov_reason = governing_offset(certified)
        gov = "0mm (on boundary)" if on else (
            f"{gov_value}mm ({gov_reason})" if gov_value is not None else "UNRESOLVED"
        )
        print(f"        model role={result.role}; model_on={result.building_on_boundary}; "
              f"envelope_on={on} ({on_fraction * 100:.0f}%){disagree}")
        print(f"        governing = {gov}")
        print(f"        certified offsets: {format_certified(certified)}")
        if dropped:
            print(f"        dropped: {format_dropped(dropped)}")
        if ignored:
            print(f"        pool dims LLM ignored (chain/other): {format_tokens(ignored)}")
        print()


def ensure_envelope(
    pdf_path: str,
    page_number: int,
    rect: fitz.Rect,
    coloured_path: str,
    input_path: str,
    zoom: float,
) -> tuple[int, int]:
    """Reuse slow image-model output when present; regenerate if missing."""
    page = fitz.open(pdf_path)[page_number]
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=rect, alpha=False)
    if pathlib_exists(input_path) and pathlib_exists(coloured_path):
        print(f"reusing envelope images: {input_path}, {coloured_path}", flush=True)
        return pix.width, pix.height
    print("generating building-envelope colour mask...", flush=True)
    return fill_building_envelope(pdf_path, page_number, rect, coloured_path, input_path, zoom)


def render_strip(page: fitz.Page, strip: fitz.Rect, out_path: str) -> None:
    zoom = min(
        4.0,
        MAX_STRIP_WIDTH_PX / strip.width,
        MAX_STRIP_HEIGHT_PX / strip.height,
    )
    page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=strip, alpha=False).save(out_path)


def pathlib_exists(path: str) -> bool:
    return Path(path).exists()


def boundary_edges_from_geometry(
    geo: PageGeometry,
    fallback_rect: fitz.Rect,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Recover the rectangular title boundary from long dashed PDF segments."""
    dashed = [s for s in geo.segments if s.is_dashed and s.length > 100]
    horizontals = [s for s in dashed if is_horizontal(s)]
    verticals = [s for s in dashed if is_vertical(s)]
    if not horizontals or not verticals:
        return [
            ((fallback_rect.x0, fallback_rect.y0), (fallback_rect.x1, fallback_rect.y0)),
            ((fallback_rect.x1, fallback_rect.y0), (fallback_rect.x1, fallback_rect.y1)),
            ((fallback_rect.x1, fallback_rect.y1), (fallback_rect.x0, fallback_rect.y1)),
            ((fallback_rect.x0, fallback_rect.y1), (fallback_rect.x0, fallback_rect.y0)),
        ]

    top_y = edge_axis_value(horizontals, "min", "y")
    bottom_y = edge_axis_value(horizontals, "max", "y")
    left_x = edge_axis_value(verticals, "min", "x")
    right_x = edge_axis_value(verticals, "max", "x")
    return [
        ((left_x, top_y), (right_x, top_y)),
        ((right_x, top_y), (right_x, bottom_y)),
        ((right_x, bottom_y), (left_x, bottom_y)),
        ((left_x, bottom_y), (left_x, top_y)),
    ]


def edge_axis_value(segments, mode: str, axis: str) -> float:
    values = [
        ((s.p0[0] + s.p1[0]) / 2) if axis == "x" else ((s.p0[1] + s.p1[1]) / 2)
        for s in segments
    ]
    target = min(values) if mode == "min" else max(values)
    near = [v for v in values if abs(v - target) < 8.0]
    return float(np.median(near))


def is_horizontal(segment) -> bool:
    return abs(segment.p1[1] - segment.p0[1]) < abs(segment.p1[0] - segment.p0[0])


def is_vertical(segment) -> bool:
    return abs(segment.p1[0] - segment.p0[0]) < abs(segment.p1[1] - segment.p0[1])


def strip_rect(a, b, cx, cy, bounds) -> fitz.Rect:
    nx, ny = inward_normal(a, b, cx, cy)
    ex, ey = b[0] - a[0], b[1] - a[1]
    length = math.hypot(ex, ey)
    tx, ty = ex / length, ey / length
    corners = [
        (bounds.x0, bounds.y0),
        (bounds.x1, bounds.y0),
        (bounds.x1, bounds.y1),
        (bounds.x0, bounds.y1),
    ]
    t_values = [dot(p, (tx, ty)) for p in corners]
    n_values = [dot(p, (nx, ny)) for p in corners]
    boundary_n = dot(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), (nx, ny))
    inward_n = boundary_n + (max(n_values) - min(n_values)) * CROP_DEPTH_FRACTION

    # Full extent along the boundary direction; half the plan inward from it.
    # The outer viewport edge is kept so exterior dimension labels remain visible.
    pts = [
        from_basis(min(t_values), min(n_values), (tx, ty), (nx, ny)),
        from_basis(max(t_values), min(n_values), (tx, ty), (nx, ny)),
        from_basis(max(t_values), inward_n, (tx, ty), (nx, ny)),
        from_basis(min(t_values), inward_n, (tx, ty), (nx, ny)),
    ]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return fitz.Rect(min(xs), min(ys), max(xs), max(ys)) & bounds


def dot(point, vector) -> float:
    return point[0] * vector[0] + point[1] * vector[1]


def from_basis(t: float, n: float, tangent, normal) -> tuple[float, float]:
    return (tangent[0] * t + normal[0] * n, tangent[1] * t + normal[1] * n)


def certify_offsets(
    offsets: list[OffsetDim],
    pool: list[TextToken],
    strip: fitz.Rect,
) -> tuple[list[CertifiedOffset], list[tuple[OffsetDim, str]]]:
    certified: list[CertifiedOffset] = []
    dropped: list[tuple[OffsetDim, str]] = []
    used_tokens: set[int] = set()
    for offset in offsets:
        matches = [(i, t) for i, t in enumerate(pool) if t.text.strip() == str(offset.value_mm)]
        if not matches:
            dropped.append((offset, "value not in extracted pool"))
            continue

        ox = strip.x0 + offset.x * strip.width
        oy = strip.y0 + offset.y * strip.height
        i, tok = min(matches, key=lambda item: math.dist(item[1].center, (ox, oy)))
        dist = math.dist(tok.center, (ox, oy))
        if dist <= TOKEN_NEAR_PT:
            note = f"location match {dist:.0f}pt"
        elif len(matches) == 1:
            note = f"value-only match; model point {dist:.0f}pt from token"
        else:
            dropped.append((offset, f"nearest same-value token {dist:.0f}pt away"))
            continue
        if i in used_tokens:
            dropped.append((offset, "duplicate claim on same PDF token"))
            continue
        used_tokens.add(i)
        certified.append(CertifiedOffset(offset, tok, dist, note))
    return certified, dropped


def ignored_pool(
    pool: list[TextToken],
    certified: list[CertifiedOffset],
    dropped: list[tuple[OffsetDim, str]],
) -> list[TextToken]:
    used = {id(c.token) for c in certified}
    dropped_values = {str(d.value_mm) for d, _ in dropped}
    return [
        token for token in pool
        if id(token) not in used and token.text.strip() not in dropped_values
    ]


def is_dimension_text(text: str) -> bool:
    stripped = text.strip()
    return stripped.isdigit() and 300 <= int(stripped) <= 50000 and len(stripped) in (3, 4, 5)


def format_certified(certified: list[CertifiedOffset]) -> str:
    if not certified:
        return "none"
    return ", ".join(
        f"{c.offset.value_mm}mm@({c.token.center[0]:.0f},{c.token.center[1]:.0f})"
        f"[{c.offset.status}; {c.note}]"
        for c in certified
    )


def label_says_existing(offset: OffsetDim) -> bool:
    """Status from the PRINTED label text (deterministic), not the model's inferred
    status field (which flips run-to-run for unmarked dims like 'nom 10800')."""
    return "existing" in offset.printed_label.lower()


def governing_offset(certified: list[CertifiedOffset]) -> tuple[int | None, str]:
    # Exclude offsets whose label says "existing" (likely existing fabric / boundary
    # wall). Proposed or unmarked labels are candidate proposed setbacks; min governs.
    candidates = [c.offset.value_mm for c in certified if not label_says_existing(c.offset)]
    if candidates:
        return min(candidates), "min of non-existing offsets"
    return None, "only 'existing' offsets (excluded)"


def format_dropped(dropped: list[tuple[OffsetDim, str]]) -> str:
    return ", ".join(f"{offset.value_mm}mm ({reason})" for offset, reason in dropped)


def format_tokens(tokens: list[TextToken]) -> str:
    return ", ".join(
        f"{t.text.strip()}@({t.center[0]:.0f},{t.center[1]:.0f})"
        for t in tokens
    ) or "none"


def inward_normal(a, b, cx, cy):
    ex, ey = b[0] - a[0], b[1] - a[1]
    n = math.hypot(ex, ey)
    nx, ny = -ey / n, ex / n
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    if (cx - mx) * nx + (cy - my) * ny < 0:
        nx, ny = -nx, -ny
    return nx, ny


def touch_fraction(a, b, cx, cy, in_mask):
    nx, ny = inward_normal(a, b, cx, cy)
    touch = total = 0
    for t in np.linspace(0.05, 0.95, 40):
        sx, sy = a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])
        d, hit = 0.0, None
        while d * MM_PER_PT < 16000:
            if in_mask(sx + nx * d, sy + ny * d):
                hit = d * MM_PER_PT
                break
            d += 2.0
        if hit is None:
            continue
        total += 1
        touch += hit < TOUCH_MM
    return touch / total if total else 0.0


def edge_label(a, b, cx, cy):
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    if abs(b[0] - a[0]) > abs(b[1] - a[1]):
        return "top" if my < cy else "bottom"
    return "left" if mx < cx else "right"


def isolate_site_plan(page: fitz.Page) -> fitz.Rect:
    render_sheet(page, "tmp/slice21_sheet.png", max_width=4000)
    located = locate_titles(page, list_titles("tmp/slice21_sheet.png"))
    labelled = label_viewports(extract_viewports(page), located)
    site = next(vp for vp in labelled if vp.title and "site plan" in vp.title.lower())
    return fitz.Rect(site.x0, site.y0, site.x1, site.y1)


if __name__ == "__main__":
    main()
