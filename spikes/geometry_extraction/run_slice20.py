"""Slice 20: per-boundary setback with FOCUSED status per offset.

Same as slice 19 (model associates offsets to sides, envelope gives on-boundary),
but each certified offset's existing/proposed status comes from a focused,
marked, per-dimension check (slice 8) instead of the unreliable broad call.
Governing = 0 if on-boundary, else the minimum PROPOSED offset.

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_slice20
"""

import math

import numpy as np
import fitz

from spikes.geometry_extraction.candidates import build_dimension_candidates
from spikes.geometry_extraction.envelope import envelope_mask, fill_building_envelope
from spikes.geometry_extraction.geometry import clip_geometry, extract_page_geometry
from spikes.geometry_extraction.verify import render_marked_crop
from spikes.geometry_extraction.viewports import (
    extract_viewports,
    label_viewports,
    locate_titles,
)
from spikes.geometry_extraction.vision import (
    assess_boundaries,
    classify_element,
    extract_boundary_polygon,
    list_titles,
    render_sheet,
)

SAMPLE_PDF = "assets/site_plan.pdf"
INPUT_PATH = "tmp/slice20_in.png"
COLOURED_PATH = "tmp/slice20_col.png"
ZOOM = 3.0
MM_PER_PT = 25.4 / 72 * 100
NEAR_PT, TOUCH_MM, ON_FRACTION = 300, 500, 0.15


def main() -> None:
    page = fitz.open(SAMPLE_PDF)[0]
    rect = isolate_site_plan(page)
    site_geo = clip_geometry(extract_page_geometry(page), rect)
    tokens = [t for t in site_geo.text_tokens if t.text.strip().isdigit()]
    boundary_segs = [s for s in site_geo.segments if s.is_dashed and s.length > 100]
    candidates = build_dimension_candidates(site_geo, 100, boundary_segs)

    wpx, hpx = fill_building_envelope(SAMPLE_PDF, 0, rect, COLOURED_PATH, INPUT_PATH, ZOOM)
    mask = envelope_mask(COLOURED_PATH, (wpx, hpx))
    report = assess_boundaries(INPUT_PATH)
    on_by_side = envelope_on_boundary(rect, wpx, hpx, mask)

    print("per-boundary setback (focused status per offset):\n")
    for s in report.sides:
        on = on_by_side.get(s.side, 0.0) >= ON_FRACTION
        resolved = []
        for o in s.offsets:
            mx, my = rect.x0 + o.x * rect.width, rect.y0 + o.y * rect.height
            if not any(t.text.strip() == str(o.value_mm)
                       and math.dist(t.center, (mx, my)) <= NEAR_PT for t in tokens):
                continue  # not certified against text
            proposed = focused_is_proposed(candidates, o.value_mm, mx, my)
            resolved.append((o.value_mm, proposed))

        proposed_vals = [v for v, p in resolved if p]
        offs = ", ".join(f"{v}mm[{'proposed' if p else 'existing/other'}]" for v, p in resolved) or "none"
        if on:
            gov = "0mm (on boundary)"
        elif proposed_vals:
            gov = f"{min(proposed_vals)}mm"
        else:
            gov = "UNRESOLVED (fail closed)"
        print(f"  {s.side} ({s.role}): governing = {gov}")
        print(f"        {'sits on boundary, except: ' if on else 'offsets: '}{offs}\n")


def focused_is_proposed(candidates, value, mx, my) -> bool:
    matches = [c for c in candidates if c.annotated_value == value and c.line]
    if not matches:
        return False
    c = min(matches, key=lambda c: math.dist(((c.line[0] + c.line[2]) / 2,
                                              (c.line[1] + c.line[3]) / 2), (mx, my)))
    box = (min(c.line[0], c.line[2]), min(c.line[1], c.line[3]),
           max(c.line[0], c.line[2]), max(c.line[1], c.line[3]))
    render_marked_crop(SAMPLE_PDF, 0, box, "tmp/s20_mark.png", margin=240, zoom=6)
    r = classify_element("tmp/s20_mark.png", value)
    return r.is_proposed_dwelling and r.confidence.lower() == "high"


def envelope_on_boundary(rect, wpx, hpx, mask) -> dict:
    poly = [(rect.x0 + v.x * rect.width, rect.y0 + v.y * rect.height)
            for v in extract_boundary_polygon(INPUT_PATH).vertices]
    cx, cy = np.mean([p[0] for p in poly]), np.mean([p[1] for p in poly])

    def in_mask(x, y):
        px, py = int((x - rect.x0) / rect.width * wpx), int((y - rect.y0) / rect.height * hpx)
        return 0 <= px < wpx and 0 <= py < hpx and bool(mask[py, px])

    out = {}
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        if math.dist(a, b) * MM_PER_PT < 3000:
            continue
        out[edge_label(a, b, cx, cy)] = touch_fraction(a, b, cx, cy, in_mask)
    return out


def touch_fraction(a, b, cx, cy, in_mask):
    ex, ey = b[0] - a[0], b[1] - a[1]
    n = math.hypot(ex, ey)
    nx, ny = -ey / n, ex / n
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    if (cx - mx) * nx + (cy - my) * ny < 0:
        nx, ny = -nx, -ny
    touch = total = 0
    for t in np.linspace(0.05, 0.95, 40):
        sx, sy = a[0] + t * ex, a[1] + t * ey
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
    render_sheet(page, "tmp/slice20_sheet.png", max_width=4000)
    located = locate_titles(page, list_titles("tmp/slice20_sheet.png"))
    labelled = label_viewports(extract_viewports(page), located)
    site = next(vp for vp in labelled if vp.title and "site plan" in vp.title.lower())
    return fitz.Rect(site.x0, site.y0, site.x1, site.y1)


if __name__ == "__main__":
    main()
