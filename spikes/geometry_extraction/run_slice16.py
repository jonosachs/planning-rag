"""Slice 16: dimensions-first setback extraction with a text-confirmation guard.

The model identifies the setback dimensions (role, what they measure to, printed
label, value). Code then confirms each value against the real PDF text - present
=> certified; absent => rejected as a hallucination (this is what would drop the
invented 1500/1780 from the earlier pure-vision test). No boundary line-fitting;
shape-agnostic.

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_slice16
"""

import fitz

from spikes.geometry_extraction.geometry import clip_geometry, extract_page_geometry
from spikes.geometry_extraction.viewports import (
    extract_viewports,
    label_viewports,
    locate_titles,
)
from spikes.geometry_extraction.vision import identify_setbacks, list_titles, render_sheet

SAMPLE_PDF = "assets/site_plan.pdf"
CROP_PATH = "tmp/slice16_crop.png"


def main() -> None:
    page = fitz.open(SAMPLE_PDF)[0]
    rect = isolate_site_plan(page)
    site_geo = clip_geometry(extract_page_geometry(page), rect)
    printed = {t.text.strip() for t in site_geo.text_tokens if t.text.strip().isdigit()}

    page.get_pixmap(matrix=fitz.Matrix(4, 4), clip=rect, alpha=False).save(CROP_PATH)
    identified = identify_setbacks(CROP_PATH)

    print(f"model identified {len(identified.setbacks)} setbacks; confirming against PDF text:\n")
    for s in identified.setbacks:
        confirmed = str(s.value_mm) in printed
        tag = "CERTIFIED" if confirmed else "REJECTED (not on sheet)"
        print(f"  {s.role:<5} {s.value_mm:>6}mm  {tag}")
        print(f"        measures_to={s.measures_to} ({s.status}); label={s.printed_label!r}")


def isolate_site_plan(page: fitz.Page) -> fitz.Rect:
    render_sheet(page, "tmp/slice16_sheet.png", max_width=4000)
    located = locate_titles(page, list_titles("tmp/slice16_sheet.png"))
    labelled = label_viewports(extract_viewports(page), located)
    site = next(vp for vp in labelled if vp.title and "site plan" in vp.title.lower())
    return fitz.Rect(site.x0, site.y0, site.x1, site.y1)


if __name__ == "__main__":
    main()
