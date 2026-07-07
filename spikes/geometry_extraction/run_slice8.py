"""Slice 8: focused per-dimension element classification (marked crop).

The whole-plan call couldn't tell the dwelling setback (10800) from a dimension
to an existing boundary wall (9100). Here each dimension is outlined in red on a
tight crop and classified on its own: what does its far end reach - the proposed
dwelling, or something else? Governing setback then counts only high-confidence
dwelling dimensions; anything else is excluded or flagged.

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_slice8
"""

import fitz

from spikes.geometry_extraction.candidates import build_dimension_candidates
from spikes.geometry_extraction.geometry import clip_geometry, extract_page_geometry
from spikes.geometry_extraction.viewports import (
    extract_viewports,
    label_viewports,
    locate_titles,
)
from spikes.geometry_extraction.vision import classify_element, list_titles, render_sheet

SAMPLE_PDF = "assets/site_plan.pdf"
SHEET_PATH = "tmp/slice8_sheet.png"
SCALE = 100
TEST_VALUES = {9100, 10800}  # the right-boundary pair to disambiguate
MARGIN_PT = 240


def main() -> None:
    page = fitz.open(SAMPLE_PDF)[0]
    geo = extract_page_geometry(page)
    rect = isolate_site_plan(page)
    if rect is None:
        print("could not isolate site plan")
        return

    site_geo = clip_geometry(geo, rect)
    boundary = [s for s in site_geo.segments if s.is_dashed and s.length > 100]
    candidates = build_dimension_candidates(site_geo, SCALE, boundary)
    targets = [c for c in candidates if c.annotated_value in TEST_VALUES and c.line]

    print(f"classifying {len(targets)} dimensions with focused marked crops:\n")
    for c in targets:
        crop_path = f"tmp/slice8_{c.annotated_value}_{c.id}.png"
        mark_and_crop(c.line, crop_path)
        result = classify_element(crop_path, c.annotated_value)
        keep = result.is_proposed_dwelling and result.confidence == "high"
        verdict = "COUNTS (dwelling setback)" if keep else "excluded / flag"
        print(f"  {c.annotated_value}mm -> {result.measures_to} "
              f"(dwelling={result.is_proposed_dwelling}, conf={result.confidence})  {verdict}")
        print(f"        {result.reasoning[:100]}\n")


def mark_and_crop(line, out_path: str) -> None:
    """Outline the dimension line in red on a fresh page and crop around it."""
    page = fitz.open(SAMPLE_PDF)[0]
    x0, y0, x1, y1 = line
    box = fitz.Rect(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
    page.draw_rect(box, color=(1, 0, 0), width=2)
    crop = fitz.Rect(box.x0 - MARGIN_PT, box.y0 - MARGIN_PT,
                     box.x1 + MARGIN_PT, box.y1 + MARGIN_PT) & page.rect
    page.get_pixmap(matrix=fitz.Matrix(6, 6), clip=crop, alpha=False).save(out_path)


def isolate_site_plan(page: fitz.Page) -> fitz.Rect | None:
    render_sheet(page, SHEET_PATH, max_width=4000)
    located = locate_titles(page, list_titles(SHEET_PATH))
    labelled = label_viewports(extract_viewports(page), located)
    site = next((vp for vp in labelled if vp.title and "site plan" in vp.title.lower()), None)
    return fitz.Rect(site.x0, site.y0, site.x1, site.y1) if site else None


if __name__ == "__main__":
    main()
