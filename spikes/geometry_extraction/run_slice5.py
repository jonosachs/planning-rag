"""Slice 5: label viewports by title, select the site plan, validate.

Combines the pieces: model lists sub-drawing titles -> code locates them in the
PDF text -> each scissor viewport is labelled by the title beneath it -> we pick
the site-plan viewport and check it holds the known setbacks at one scale.

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_slice5
"""

import fitz

from spikes.geometry_extraction.geometry import extract_page_geometry
from spikes.geometry_extraction.measure import points_to_mm
from spikes.geometry_extraction.candidates import build_dimension_candidates
from spikes.geometry_extraction.viewports import (
    extract_viewports,
    label_viewports,
    locate_titles,
)
from spikes.geometry_extraction.vision import list_titles, render_sheet

SAMPLE_PDF = "assets/site_plan.pdf"
RENDER_PATH = "tmp/slice5_sheet.png"
KNOWN_SETBACKS = {4400, 1030, 2825, 10800}


def main() -> None:
    page = fitz.open(SAMPLE_PDF)[0]
    geo = extract_page_geometry(page)

    render_sheet(page, RENDER_PATH, max_width=4000)
    titles = list_titles(RENDER_PATH)
    located = locate_titles(page, titles)
    labelled = label_viewports(extract_viewports(page), located)

    print(f"{len(titles)} titles, {len(labelled)} viewports labelled:")
    for vp in labelled:
        print(f"  ({vp.x0:.0f},{vp.y0:.0f})-({vp.x1:.0f},{vp.y1:.0f})  title={vp.title!r}")

    site = next((vp for vp in labelled if vp.title and "site plan" in vp.title.lower()), None)
    if site is None:
        print("\nno viewport labelled as the site plan")
        return

    rect = fitz.Rect(site.x0, site.y0, site.x1, site.y1)
    dims = sorted({int(t.text) for t in geo.text_tokens
                   if rect.contains(fitz.Point(t.center))
                   and t.text.isdigit() and len(t.text) in (3, 4, 5)})
    found = KNOWN_SETBACKS & set(dims)
    print(f"\nsite-plan viewport: ({rect.x0:.0f},{rect.y0:.0f})-({rect.x1:.0f},{rect.y1:.0f})")
    print(f"dims in viewport: {dims}")
    print(f"known setbacks present: {sorted(found)}  ({len(found)}/{len(KNOWN_SETBACKS)})")
    print(f"validate scale: {infer_scale(geo, rect)}")


def infer_scale(geo, rect) -> str:
    """Scale is consistent if annotated text ~= measured span at that scale."""
    boundary = [s for s in geo.segments if s.is_dashed and s.length > 100]
    in_geo = geo.model_copy(update={
        "segments": [s for s in geo.segments
                     if rect.contains(fitz.Point((s.p0[0] + s.p1[0]) / 2,
                                                 (s.p0[1] + s.p1[1]) / 2))],
        "text_tokens": [t for t in geo.text_tokens if rect.contains(fitz.Point(t.center))],
    })
    cands = build_dimension_candidates(in_geo, 100, boundary)
    agree = sum(1 for c in cands if abs(c.measured_mm - c.annotated_value) / c.annotated_value < 0.03)
    return f"{agree}/{len(cands)} dims agree with annotation at 1:100"


if __name__ == "__main__":
    main()
