"""Slice 15: on-boundary condition for ALL boundaries.

Generalises slice 14 to every edge of the site boundary (any orientation).
Vision traces the boundary polygon and colours the building envelope; code marches
inward from each boundary edge to the envelope mask and reports, per edge,
how much of it the building sits on.

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_slice15
"""

import numpy as np
import fitz

from spikes.geometry_extraction.envelope import envelope_mask, fill_building_envelope
from spikes.geometry_extraction.viewports import (
    extract_viewports,
    label_viewports,
    locate_titles,
)
from spikes.geometry_extraction.vision import (
    extract_boundary_polygon,
    list_titles,
    render_sheet,
)

SAMPLE_PDF = "assets/site_plan.pdf"
INPUT_PATH = "tmp/slice15_in.png"
COLOURED_PATH = "tmp/slice15_col.png"
ZOOM = 3.0
MM_PER_PT = 25.4 / 72 * 100
TOUCH_MM = 500
MAX_MARCH_MM = 16000


def main() -> None:
    page = fitz.open(SAMPLE_PDF)[0]
    rect = isolate_site_plan(page)
    wpx, hpx = fill_building_envelope(SAMPLE_PDF, 0, rect, COLOURED_PATH, INPUT_PATH, ZOOM)
    mask = envelope_mask(COLOURED_PATH, (wpx, hpx))

    poly = [(rect.x0 + v.x * rect.width, rect.y0 + v.y * rect.height)
            for v in extract_boundary_polygon(INPUT_PATH).vertices]
    if len(poly) < 3:
        print("no boundary polygon from vision")
        return
    cx = np.mean([p[0] for p in poly])
    cy = np.mean([p[1] for p in poly])

    def in_mask(x, y):
        px = int((x - rect.x0) / rect.width * wpx)
        py = int((y - rect.y0) / rect.height * hpx)
        return 0 <= px < wpx and 0 <= py < hpx and bool(mask[py, px])

    print(f"{len(poly)} boundary edges:\n")
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        length = np.hypot(b[0] - a[0], b[1] - a[1])
        if length * MM_PER_PT < 3000:  # skip tiny edges
            continue
        report_edge(edge_label(a, b, cx, cy), a, b, cx, cy, in_mask)


def report_edge(label, a, b, cx, cy, in_mask):
    nx, ny = inward_normal(a, b, cx, cy)
    touching, setbacks, samples = 0, [], 0
    for t in np.linspace(0.05, 0.95, 40):
        sx, sy = a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])
        gap = march(sx, sy, nx, ny, in_mask)
        if gap is None:
            continue
        samples += 1
        if gap < TOUCH_MM:
            touching += 1
        else:
            setbacks.append(gap)
    if samples == 0:
        print(f"  {label}: no building found off this edge")
        return
    pct = 100 * touching / samples
    typ = f"; typical set-back ~{round(np.median(setbacks) / 100) * 100:.0f}mm" if setbacks else ""
    print(f"  {label}: on boundary {pct:.0f}% of built length{typ}")


def march(sx, sy, nx, ny, in_mask):
    step = 2.0
    d = 0.0
    while d * MM_PER_PT < MAX_MARCH_MM:
        if in_mask(sx + nx * d, sy + ny * d):
            return d * MM_PER_PT
        d += step
    return None


def inward_normal(a, b, cx, cy):
    ex, ey = b[0] - a[0], b[1] - a[1]
    n = np.hypot(ex, ey)
    nx, ny = -ey / n, ex / n
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    if (cx - mx) * nx + (cy - my) * ny < 0:  # flip to point toward interior
        nx, ny = -nx, -ny
    return nx, ny


def edge_label(a, b, cx, cy):
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    horizontal = abs(b[0] - a[0]) > abs(b[1] - a[1])
    if horizontal:
        return "top edge" if my < cy else "bottom edge"
    return "left edge" if mx < cx else "right edge"


def isolate_site_plan(page: fitz.Page) -> fitz.Rect:
    render_sheet(page, "tmp/slice15_sheet.png", max_width=4000)
    located = locate_titles(page, list_titles("tmp/slice15_sheet.png"))
    labelled = label_viewports(extract_viewports(page), located)
    site = next(vp for vp in labelled if vp.title and "site plan" in vp.title.lower())
    return fitz.Rect(site.x0, site.y0, site.x1, site.y1)


if __name__ == "__main__":
    main()
