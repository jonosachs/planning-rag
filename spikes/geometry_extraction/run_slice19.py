"""Slice 19: per-boundary "on boundary, except [offsets]".

The model assesses each side (on-boundary + the offsets along it - it associates
them semantically, no geometric attachment). Code certifies each offset value
against the PDF text. The envelope gives the authoritative on-boundary and
cross-checks the model. Output per side: on boundary except the certified
offsets, or set back by the minimum proposed offset.

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_slice19
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
    assess_boundaries,
    extract_boundary_polygon,
    list_titles,
    render_sheet,
)

SAMPLE_PDF = "assets/site_plan.pdf"
INPUT_PATH = "tmp/slice19_in.png"
COLOURED_PATH = "tmp/slice19_col.png"
ZOOM = 3.0
MM_PER_PT = 25.4 / 72 * 100
NEAR_PT, TOUCH_MM, ON_FRACTION = 300, 500, 0.15


def main() -> None:
    page = fitz.open(SAMPLE_PDF)[0]
    rect = isolate_site_plan(page)
    site_geo = clip_geometry(extract_page_geometry(page), rect)
    tokens = [t for t in site_geo.text_tokens if t.text.strip().isdigit()]

    wpx, hpx = fill_building_envelope(SAMPLE_PDF, 0, rect, COLOURED_PATH, INPUT_PATH, ZOOM)
    mask = envelope_mask(COLOURED_PATH, (wpx, hpx))
    report = assess_boundaries(INPUT_PATH)
    on_by_side = envelope_on_boundary(rect, wpx, hpx, mask)

    print("per-boundary setback (on boundary, except offsets):\n")
    for s in report.sides:
        certified = [o for o in s.offsets if certify(o, rect, tokens)]
        on = on_by_side.get(s.side, 0.0) >= ON_FRACTION
        flag = "" if on == s.building_on_boundary else "  [model/envelope disagree]"
        proposed = [o.value_mm for o in certified if o.status.startswith("propos")]

        offs = ", ".join(f"{o.value_mm}mm[{o.status}]" for o in certified) or "none"
        if on:
            gov = "0mm (on boundary)"
            line = f"sits on boundary, except: {offs}"
        elif proposed:
            gov = f"{min(proposed)}mm"
            line = f"set back; offsets: {offs}"
        else:
            gov = "UNRESOLVED (fail closed)"
            line = f"offsets: {offs}"
        print(f"  {s.side} ({s.role}): governing = {gov}{flag}")
        print(f"        {line}\n")


def certify(offset, rect, tokens) -> bool:
    mx, my = rect.x0 + offset.x * rect.width, rect.y0 + offset.y * rect.height
    matches = [t for t in tokens if t.text.strip() == str(offset.value_mm)]
    return any(math.dist(t.center, (mx, my)) <= NEAR_PT for t in matches)


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
        d = 0.0
        hit = None
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
    render_sheet(page, "tmp/slice19_sheet.png", max_width=4000)
    located = locate_titles(page, list_titles("tmp/slice19_sheet.png"))
    labelled = label_viewports(extract_viewports(page), located)
    site = next(vp for vp in labelled if vp.title and "site plan" in vp.title.lower())
    return fitz.Rect(site.x0, site.y0, site.x1, site.y1)


if __name__ == "__main__":
    main()
