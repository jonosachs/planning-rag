"""Slice 2: model picks a region, code extracts geometry only there.

Tests the coarse-to-fine step: can the model localise the right region for a
question, such that the clipped geometry contains the features needed (for a
setback: the boundary AND a building wall)? The model only points; extraction
and any measurement stay deterministic.

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_slice2
"""

import fitz

from spikes.geometry_extraction.geometry import extract_page_geometry
from spikes.geometry_extraction.schemas import RegionChoice
from spikes.geometry_extraction.vision import pick_region, region_to_rect, render_sheet

SAMPLE_PDF = "assets/site_plan.pdf"
RENDER_PATH = "tmp/slice2_sheet.png"
QUESTION = "What is the front setback of the proposed building from the title boundary?"


def main() -> None:
    page = fitz.open(SAMPLE_PDF)[0]
    geo = extract_page_geometry(page)

    render_sheet(page, RENDER_PATH)
    region = pick_region(QUESTION, RENDER_PATH)
    rect = region_to_rect(region, page)

    print(f"question: {QUESTION}")
    print(f"region reason: {region.reason}")
    print(f"expected_features: {region.expected_features}")
    print(f"region bbox (page fractions): "
          f"({region.x0:.2f},{region.y0:.2f})-({region.x1:.2f},{region.y1:.2f})")

    in_segs = [s for s in geo.segments if rect.contains(midpoint(s))]
    in_toks = [t for t in geo.text_tokens if rect.contains(t.center)]
    dashed = [s for s in in_segs if s.is_dashed and s.length > 100]
    dims = [t for t in in_toks if t.text.strip().isdigit() and len(t.text.strip()) in (3, 4, 5)]

    print(f"\nsegments in region: {len(in_segs)} / {len(geo.segments)} "
          f"({100 * len(in_segs) / len(geo.segments):.0f}% of sheet)")
    print(f"long dashed segments (boundary candidates): {len(dashed)}")
    print(f"dimension-like tokens in region: {len(dims)}")
    verdict = "region contains boundary candidates + dimensions" if dashed and dims \
        else "region MISSING boundary or dimensions - localisation failed"
    print(f"verdict: {verdict}")


def midpoint(segment) -> fitz.Point:
    (x0, y0), (x1, y1) = segment.p0, segment.p1
    return fitz.Point((x0 + x1) / 2, (y0 + y1) / 2)


if __name__ == "__main__":
    main()
