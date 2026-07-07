"""Slice 7: per-boundary setback assessment with dwelling/existing filtering.

Isolate the site-plan viewport, build single-scale dimension candidates, then a
single vision call judges each boundary's on/offset condition from the image and
classifies every attached dimension (what it measures to + status). Code then
computes the governing setback deterministically = 0 if the dwelling is on the
boundary, else the minimum of dimensions that measure boundary -> proposed
dwelling. A dimension to an existing wall/fence/setout is excluded, so the right
boundary resolves to 10800 (house), not 9100 (existing boundary wall).

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_slice7
"""

import fitz

from spikes.geometry_extraction.candidates import build_dimension_candidates
from spikes.geometry_extraction.geometry import clip_geometry, extract_page_geometry
from spikes.geometry_extraction.schemas import BoundarySetback
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
    known = {c.annotated_value for c in candidates}

    pix = page.get_pixmap(matrix=fitz.Matrix(4, 4), clip=pad(rect, page), alpha=False)
    pix.save(CROP_PATH)

    assessment = assess_setbacks(CROP_PATH, candidates)
    print(f"{len(candidates)} candidates; per-boundary setbacks:\n")
    for b in assessment.boundaries:
        gov = governing_setback(b)
        gov_str = "0mm (on boundary)" if gov == 0 else (f"{gov}mm" if gov else "undimensioned")
        print(f"  {b.side:<7} ({b.compass or '?'}): governing = {gov_str}")
        for d in b.dimensions:
            mark = "setback" if d.counts_as_setback else "excluded"
            flag = "  [!] not a candidate value" if d.value_mm not in known else ""
            print(f"        {d.value_mm:>6}mm  {mark:<8} -> {d.measures_to} ({d.status}){flag}")
        print()


def governing_setback(b: BoundarySetback) -> int | None:
    if b.building_on_boundary:
        return 0
    setbacks = [d.value_mm for d in b.dimensions if d.counts_as_setback]
    return min(setbacks) if setbacks else None


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
