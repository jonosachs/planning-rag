"""Slice 10: on/offset condition via hatching, clean crop.

The wall-on-boundary line is invisible (it coincides with the boundary), so
instead we use the visible fill: building/paved areas are hatched, garden/grass
is a light stipple. Ask whether building hatching meets the top boundary or grass
separates them. Clean crop (no marker over the linework), whole site-plan
drawing, temperature 0, run twice.

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_slice10
"""

import fitz

from spikes.geometry_extraction.geometry import clip_geometry, extract_page_geometry
from spikes.geometry_extraction.viewports import (
    extract_viewports,
    label_viewports,
    locate_titles,
)
from spikes.geometry_extraction.verify import verify_feature
from spikes.geometry_extraction.vision import list_titles, render_sheet

SAMPLE_PDF = "assets/site_plan.pdf"

HATCH_Q = (
    "The title boundary is the line running along the very top of this drawing. "
    "Building and paved areas are shown with dense/solid hatching; garden and "
    "grass areas are shown with a light green stippled fill. Looking along the top "
    "boundary, does the BUILDING (hatched/paved area) meet the boundary directly "
    "anywhere - with no grass between them - or is there grass/garden separating "
    "the building from the boundary along its whole length? "
    "holds = true if any building/paved area meets the top boundary."
)


def main() -> None:
    page = fitz.open(SAMPLE_PDF)[0]
    geo = extract_page_geometry(page)
    rect = isolate_site_plan(page)
    site_geo = clip_geometry(geo, rect)

    box = north_boundary_box(site_geo)
    bound = (rect.x0, rect.y0, rect.x1, rect.y1)
    print("north on/offset via hatching, clean crop, twice @ temp 0:")
    for i in (1, 2):
        v = verify_feature(SAMPLE_PDF, 0, box, HATCH_Q, f"tmp/slice10_north_{i}.png",
                           margin=1000, bound=bound, mark=False)
        print(f"  run {i}: building_meets_boundary={v.holds} conf={v.confidence}")
        print(f"          {v.finding[:90]}")


def north_boundary_box(site_geo) -> tuple[float, float, float, float]:
    def is_h(s):
        return abs(s.p1[1] - s.p0[1]) < abs(s.p1[0] - s.p0[0])
    hb = [s for s in site_geo.segments if s.is_dashed and s.length > 60 and is_h(s)]
    ytop = min((s.p0[1] + s.p1[1]) / 2 for s in hb)
    north = [s for s in hb if abs((s.p0[1] + s.p1[1]) / 2 - ytop) < 8]
    xs = [c for s in north for c in (s.p0[0], s.p1[0])]
    ys = [c for s in north for c in (s.p0[1], s.p1[1])]
    return (min(xs), min(ys) - 4, max(xs), max(ys) + 4)


def isolate_site_plan(page: fitz.Page) -> fitz.Rect:
    render_sheet(page, "tmp/slice10_sheet.png", max_width=4000)
    located = locate_titles(page, list_titles("tmp/slice10_sheet.png"))
    labelled = label_viewports(extract_viewports(page), located)
    site = next(vp for vp in labelled if vp.title and "site plan" in vp.title.lower())
    return fitz.Rect(site.x0, site.y0, site.x1, site.y1)


if __name__ == "__main__":
    main()
