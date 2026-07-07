"""Slice 6: end-to-end setback answer on the isolated site-plan viewport.

Pipeline: isolate the site-plan viewport (slice 5) -> build single-scale
dimension candidates there -> model selects the one answering the question
(slice 3) -> report the annotated value as the answer with the geometric
measurement as an independent validator.

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_slice6
"""

import fitz

from spikes.geometry_extraction.candidates import build_dimension_candidates
from spikes.geometry_extraction.geometry import clip_geometry, extract_page_geometry
from spikes.geometry_extraction.viewports import (
    extract_viewports,
    label_viewports,
    locate_titles,
)
from spikes.geometry_extraction.vision import list_titles, render_sheet, select_dimension

SAMPLE_PDF = "assets/site_plan.pdf"
RENDER_PATH = "tmp/slice6_sheet.png"
SCALE = 100
QUESTION = "What is the setback of the building/courtyard from the north (title) boundary?"


def main() -> None:
    page = fitz.open(SAMPLE_PDF)[0]
    geo = extract_page_geometry(page)

    site_rect = isolate_site_plan(page, geo)
    if site_rect is None:
        print("could not isolate the site-plan viewport")
        return

    site_geo = clip_geometry(geo, site_rect)
    boundary = [s for s in site_geo.segments if s.is_dashed and s.length > 100]
    candidates = build_dimension_candidates(site_geo, SCALE, boundary)
    print(f"site-plan viewport isolated; {len(candidates)} single-scale candidates")

    selection = select_dimension(QUESTION, candidates)
    chosen = next((c for c in candidates if c.id == selection.answer_candidate_id), None)

    print(f"\nquestion: {QUESTION}")
    print(f"classification: {selection.classification}")
    print(f"reason: {selection.reason}")
    if chosen is None:
        print("answer: none selected")
        return

    agree = abs(chosen.measured_mm - chosen.annotated_value) / chosen.annotated_value < 0.03
    print(f"\nANSWER: {chosen.annotated_value} mm (drafter-annotated)")
    print(f"validation: geometry measures {chosen.measured_mm} mm at 1:{SCALE} "
          f"-> {'CONFIRMED' if agree else 'MISMATCH (flag)'}")
    print(f"nearby labels: {chosen.nearby_labels}")


def isolate_site_plan(page: fitz.Page, geo) -> fitz.Rect | None:
    render_sheet(page, RENDER_PATH, max_width=4000)
    located = locate_titles(page, list_titles(RENDER_PATH))
    labelled = label_viewports(extract_viewports(page), located)
    site = next((vp for vp in labelled if vp.title and "site plan" in vp.title.lower()), None)
    return fitz.Rect(site.x0, site.y0, site.x1, site.y1) if site else None


if __name__ == "__main__":
    main()
