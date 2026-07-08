"""Slice 11: on-boundary via measurement, not perception.

Vision only locates rough regions (building outline + top boundary) - no values,
no linetype/hatch conventions. Code then measures the vertical gap from the
boundary down to the building outline across the north edge. On-boundary falls
out as gap ~= 0; a recess shows as a jump in the gap. This turns the "is the wall
on the boundary" perception problem (which fails - the lines coincide) into an
arithmetic one.

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_slice11
"""

import numpy as np
import fitz

from spikes.geometry_extraction.geometry import extract_page_geometry
from spikes.geometry_extraction.viewports import (
    extract_viewports,
    label_viewports,
    locate_titles,
)
from spikes.geometry_extraction.vision import extract_site_regions, list_titles, render_sheet

SAMPLE_PDF = "assets/site_plan.pdf"
CROP_PATH = "tmp/slice11_siteplan.png"
MM_PER_PT = 25.4 / 72 * 100  # 1:100
ON_BOUNDARY_MM = 300  # gap below this counts as "on boundary"


def main() -> None:
    page = fitz.open(SAMPLE_PDF)[0]
    rect = isolate_site_plan(page)
    page.get_pixmap(matrix=fitz.Matrix(6, 6), clip=rect, alpha=False).save(CROP_PATH)

    regions = extract_site_regions(CROP_PATH)
    building = [to_page(v, rect) for v in regions.building_polygon]
    boundary = [to_page(v, rect) for v in regions.boundary_top_line]
    if len(building) < 3 or len(boundary) < 2:
        print("vision did not return usable regions")
        return

    by = np.mean([p[1] for p in boundary])  # north boundary y (page pt)
    bx0, bx1 = min(p[0] for p in boundary), max(p[0] for p in boundary)

    print(f"north boundary y={by:.0f}, x=[{bx0:.0f},{bx1:.0f}]  gap profile below:")
    prev = None
    for x in np.linspace(bx0 + 5, bx1 - 5, 40):
        top = building_top_at(building, x)
        if top is None:
            band = "no building"
        else:
            gap_mm = max(0.0, (top - by) * MM_PER_PT)
            band = "ON BOUNDARY (~0)" if gap_mm < ON_BOUNDARY_MM else f"set back ~{round(gap_mm/50)*50}mm"
        if band != prev:
            print(f"  x={x:.0f}: {band}")
        prev = band


def building_top_at(poly, x):
    """Topmost (min-y) point where a vertical line at x crosses the polygon edges."""
    ys = []
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if x0 == x1:
            continue
        if min(x0, x1) <= x <= max(x0, x1):
            t = (x - x0) / (x1 - x0)
            ys.append(y0 + t * (y1 - y0))
    return min(ys) if ys else None


def to_page(vertex, rect):
    return (rect.x0 + vertex.x * rect.width, rect.y0 + vertex.y * rect.height)


def isolate_site_plan(page: fitz.Page) -> fitz.Rect:
    render_sheet(page, "tmp/slice11_sheet.png", max_width=4000)
    located = locate_titles(page, list_titles("tmp/slice11_sheet.png"))
    labelled = label_viewports(extract_viewports(page), located)
    site = next(vp for vp in labelled if vp.title and "site plan" in vp.title.lower())
    return fitz.Rect(site.x0, site.y0, site.x1, site.y1)


if __name__ == "__main__":
    main()
