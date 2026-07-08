"""Slice 12: snap the rough vision region onto real geometry, then measure.

Slice 11 measured a gap to vision's rough building outline - right shape, noisy.
Here, at each sample the rough vision edge is snapped to the nearest actual drawn
line before measuring. Vision supplies the semantics (this is the building edge,
not the paving); snapping supplies the precision. No linetype/hatch - snapping
just locks a rough estimate onto whatever line is actually there.

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_slice12
"""

import numpy as np
import fitz

from spikes.geometry_extraction.geometry import clip_geometry, extract_page_geometry
from spikes.geometry_extraction.viewports import (
    extract_viewports,
    label_viewports,
    locate_titles,
)
from spikes.geometry_extraction.vision import extract_site_regions, list_titles, render_sheet

SAMPLE_PDF = "assets/site_plan.pdf"
CROP_PATH = "tmp/slice12_siteplan.png"
MM_PER_PT = 25.4 / 72 * 100
ON_BOUNDARY_MM = 250
SNAP_TOL_PT = 45


def main() -> None:
    page = fitz.open(SAMPLE_PDF)[0]
    rect = isolate_site_plan(page)
    geo = clip_geometry(extract_page_geometry(page), rect)
    page.get_pixmap(matrix=fitz.Matrix(6, 6), clip=rect, alpha=False).save(CROP_PATH)

    regions = extract_site_regions(CROP_PATH)
    building = [to_page(v, rect) for v in regions.building_polygon]
    boundary = [to_page(v, rect) for v in regions.boundary_top_line]
    hsegs = [s for s in geo.segments if is_h(s) and s.length > 8]

    bvis = float(np.mean([p[1] for p in boundary]))
    bx0, bx1 = min(p[0] for p in boundary), max(p[0] for p in boundary)

    print("north gap profile (vision edge snapped to real geometry):")
    prev = None
    for x in np.linspace(bx0 + 5, bx1 - 5, 40):
        by = snap_y(x, bvis, hsegs, above=None) or bvis
        vy = building_top_at(building, x)
        band = "no building"
        if vy is not None:
            wall = snap_y(x, vy, hsegs, above=by + 2)
            if wall is not None:
                gap = max(0.0, (wall - by) * MM_PER_PT)
                band = "ON BOUNDARY (~0)" if gap < ON_BOUNDARY_MM else f"set back ~{round(gap/50)*50}mm"
        if band != prev:
            print(f"  x={x:.0f}: {band}")
        prev = band


def snap_y(x, y_est, segs, above):
    """Nearest horizontal segment's y at x, within tolerance of y_est (and below `above`)."""
    best = None
    for s in segs:
        y = seg_y_at_x(s, x)
        if y is None or (above is not None and y <= above):
            continue
        d = abs(y - y_est)
        if d <= SNAP_TOL_PT and (best is None or d < best[0]):
            best = (d, y)
    return best[1] if best else None


def seg_y_at_x(s, x):
    (x0, y0), (x1, y1) = s.p0, s.p1
    if x0 == x1 or not (min(x0, x1) <= x <= max(x0, x1)):
        return None
    return y0 + (x - x0) / (x1 - x0) * (y1 - y0)


def building_top_at(poly, x):
    ys = []
    for i in range(len(poly)):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % len(poly)]
        if x0 != x1 and min(x0, x1) <= x <= max(x0, x1):
            ys.append(y0 + (x - x0) / (x1 - x0) * (y1 - y0))
    return min(ys) if ys else None


def is_h(s):
    return abs(s.p1[1] - s.p0[1]) < abs(s.p1[0] - s.p0[0])


def to_page(v, rect):
    return (rect.x0 + v.x * rect.width, rect.y0 + v.y * rect.height)


def isolate_site_plan(page):
    render_sheet(page, "tmp/slice12_sheet.png", max_width=4000)
    located = locate_titles(page, list_titles("tmp/slice12_sheet.png"))
    labelled = label_viewports(extract_viewports(page), located)
    site = next(vp for vp in labelled if vp.title and "site plan" in vp.title.lower())
    return fitz.Rect(site.x0, site.y0, site.x1, site.y1)


if __name__ == "__main__":
    main()
