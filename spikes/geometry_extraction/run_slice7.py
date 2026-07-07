"""Slice 7: per-boundary setback assessment (condition + dimensions).

Isolate the site-plan viewport, build single-scale dimension candidates, then a
single vision call judges each boundary's on/offset condition from the image
while taking values only from the candidates. Governing setback per boundary =
0 if on boundary, else the minimum dimensioned setback. This fixes the original
bug where one dimensioned recess (2825) was reported as "the" setback while the
building is actually on the north boundary (0).

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_slice7
"""

import fitz

from spikes.geometry_extraction.candidates import build_dimension_candidates
from spikes.geometry_extraction.geometry import clip_geometry, extract_page_geometry
from spikes.geometry_extraction.viewports import (
    extract_viewports,
    label_viewports,
    locate_titles,
)
from spikes.geometry_extraction.vision import assess_setbacks, list_titles, render_sheet

SAMPLE_PDF = "assets/site_plan.pdf"
SHEET_PATH = "tmp/slice7_sheet.png"
CROP_PATH = "tmp/slice7_siteplan.png"
SCALE = 100


def main() -> None:
    page = fitz.open(SAMPLE_PDF)[0]
    geo = extract_page_geometry(page)

    rect = isolate_site_plan(page)
    if rect is None:
        print("could not isolate the site-plan viewport")
        return

    site_geo = clip_geometry(geo, rect)
    boundary = [s for s in site_geo.segments if s.is_dashed and s.length > 100]
    candidates = build_dimension_candidates(site_geo, SCALE, boundary)

    # high-res crop of just the site plan for the visual condition judgement
    pix = page.get_pixmap(matrix=fitz.Matrix(4, 4), clip=pad(rect, page), alpha=False)
    pix.save(CROP_PATH)

    assessment = assess_setbacks(CROP_PATH, candidates)
    known = {c.annotated_value for c in candidates}

    print(f"{len(candidates)} candidates; per-boundary setbacks:\n")
    for b in assessment.boundaries:
        invented = [v for v in b.dimensioned_setbacks_mm if v not in known]
        flag = f"  [!] invented values not in candidates: {invented}" if invented else ""
        on = "ON BOUNDARY" if b.building_on_boundary else "offset"
        print(f"  {b.side:<7} ({b.compass or '?'}): {on}  governing={b.governing_setback_mm}mm  "
              f"dimensioned={b.dimensioned_setbacks_mm}{flag}")
        print(f"          {b.reasoning[:100]}")


def isolate_site_plan(page: fitz.Page) -> fitz.Rect | None:
    render_sheet(page, SHEET_PATH, max_width=4000)
    located = locate_titles(page, list_titles(SHEET_PATH))
    labelled = label_viewports(extract_viewports(page), located)
    site = next((vp for vp in labelled if vp.title and "site plan" in vp.title.lower()), None)
    return fitz.Rect(site.x0, site.y0, site.x1, site.y1) if site else None


def pad(rect: fitz.Rect, page: fitz.Page, m: float = 20) -> fitz.Rect:
    return fitz.Rect(rect.x0 - m, rect.y0 - m, rect.x1 + m, rect.y1 + m) & page.rect


if __name__ == "__main__":
    main()
