"""Slice 18: combined per-boundary setback (dimensioned + zero/on-boundary).

Wires the two paths together:
  - dimensions-first extractor (slice 16/17): certified dimensioned setbacks,
    each attached to the nearest boundary edge by its token position.
  - envelope touch check (slice 14/15): where the building sits ON a boundary,
    add a 0mm setback that has no dimension.
Governing per boundary = min(0 if on-boundary, proposed dimensioned setbacks);
fail closed (unresolved) if a boundary has neither.

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_slice18
"""

import math

import numpy as np
import fitz

from spikes.geometry_extraction.envelope import envelope_mask, fill_building_envelope
from spikes.geometry_extraction.geometry import clip_geometry, extract_page_geometry
from spikes.geometry_extraction.viewports import (
    extract_viewports,
    label_viewports,
    locate_titles,
)
from spikes.geometry_extraction.vision import (
    extract_boundary_polygon,
    identify_setbacks,
    list_titles,
    render_sheet,
)

SAMPLE_PDF = "assets/site_plan.pdf"
INPUT_PATH = "tmp/slice18_in.png"
COLOURED_PATH = "tmp/slice18_col.png"
ZOOM = 3.0
MM_PER_PT = 25.4 / 72 * 100
NEAR_PT = 250
TOUCH_MM = 500
ON_BOUNDARY_FRACTION = 0.15  # building on >=15% of an edge => that edge has a 0 setback


def main() -> None:
    page = fitz.open(SAMPLE_PDF)[0]
    rect = isolate_site_plan(page)
    site_geo = clip_geometry(extract_page_geometry(page), rect)
    tokens = [t for t in site_geo.text_tokens if t.text.strip().isdigit()]

    # image inputs
    wpx, hpx = fill_building_envelope(SAMPLE_PDF, 0, rect, COLOURED_PATH, INPUT_PATH, ZOOM)
    mask = envelope_mask(COLOURED_PATH, (wpx, hpx))
    certified = certify_setbacks(identify_setbacks(INPUT_PATH).setbacks, rect, tokens)
    poly = [(rect.x0 + v.x * rect.width, rect.y0 + v.y * rect.height)
            for v in extract_boundary_polygon(INPUT_PATH).vertices]

    cx, cy = np.mean([p[0] for p in poly]), np.mean([p[1] for p in poly])
    edges = [(poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly))]
    edges = [e for e in edges if math.dist(e[0], e[1]) * MM_PER_PT > 3000]

    def in_mask(x, y):
        px, py = int((x - rect.x0) / rect.width * wpx), int((y - rect.y0) / rect.height * hpx)
        return 0 <= px < wpx and 0 <= py < hpx and bool(mask[py, px])

    print("per-boundary setbacks (dimensioned + on-boundary):\n")
    for a, b in edges:
        label = edge_label(a, b, cx, cy)
        on_frac = touch_fraction(a, b, cx, cy, in_mask)
        attached = [(s, tok) for (s, tok) in certified if nearest_edge(tok.center, edges) == (a, b)]
        proposed = [s.value_mm for (s, tok) in attached if s.status.startswith("propos")]

        parts = []
        if on_frac >= ON_BOUNDARY_FRACTION:
            parts.append(f"0mm (wall on boundary, {on_frac*100:.0f}% of edge)")
        for s, tok in attached:
            parts.append(f"{s.value_mm}mm [{s.status}]")

        gov = 0 if on_frac >= ON_BOUNDARY_FRACTION else (min(proposed) if proposed else None)
        gov_s = f"{gov}mm" if gov is not None else "UNRESOLVED (fail closed)"
        print(f"  {label}: governing setback = {gov_s}")
        print(f"        evidence: {parts or ['none']}\n")


def certify_setbacks(setbacks, rect, tokens):
    out = []
    for s in setbacks:
        mx, my = rect.x0 + s.x * rect.width, rect.y0 + s.y * rect.height
        matches = [t for t in tokens if t.text.strip() == str(s.value_mm)]
        if not matches:
            continue
        tok = min(matches, key=lambda t: math.dist(t.center, (mx, my)))
        if math.dist(tok.center, (mx, my)) <= NEAR_PT:
            out.append((s, tok))
    return out


def nearest_edge(pt, edges):
    return min(edges, key=lambda e: pt_seg_dist(pt, e[0], e[1]))


def pt_seg_dist(p, a, b):
    (px, py), (x0, y0), (x1, y1) = p, a, b
    dx, dy = x1 - x0, y1 - y0
    if dx == dy == 0:
        return math.dist(p, a)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / (dx * dx + dy * dy)))
    return math.dist(p, (x0 + t * dx, y0 + t * dy))


def touch_fraction(a, b, cx, cy, in_mask):
    nx, ny = inward_normal(a, b, cx, cy)
    touch, total = 0, 0
    for t in np.linspace(0.05, 0.95, 40):
        sx, sy = a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])
        gap = march(sx, sy, nx, ny, in_mask)
        if gap is None:
            continue
        total += 1
        touch += gap < TOUCH_MM
    return touch / total if total else 0.0


def march(sx, sy, nx, ny, in_mask):
    d = 0.0
    while d * MM_PER_PT < 16000:
        if in_mask(sx + nx * d, sy + ny * d):
            return d * MM_PER_PT
        d += 2.0
    return None


def inward_normal(a, b, cx, cy):
    ex, ey = b[0] - a[0], b[1] - a[1]
    n = math.hypot(ex, ey)
    nx, ny = -ey / n, ex / n
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    if (cx - mx) * nx + (cy - my) * ny < 0:
        nx, ny = -nx, -ny
    return nx, ny


def edge_label(a, b, cx, cy):
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    if abs(b[0] - a[0]) > abs(b[1] - a[1]):
        return "top edge" if my < cy else "bottom edge"
    return "left edge" if mx < cx else "right edge"


def isolate_site_plan(page: fitz.Page) -> fitz.Rect:
    render_sheet(page, "tmp/slice18_sheet.png", max_width=4000)
    located = locate_titles(page, list_titles("tmp/slice18_sheet.png"))
    labelled = label_viewports(extract_viewports(page), located)
    site = next(vp for vp in labelled if vp.title and "site plan" in vp.title.lower())
    return fitz.Rect(site.x0, site.y0, site.x1, site.y1)


if __name__ == "__main__":
    main()
