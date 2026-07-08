"""Slice 14: does the building touch the boundary? (image-gen envelope mask)

Uses the image model to colour the building envelope, thresholds it to a dense
mask, and checks along the north boundary whether the building reaches it. This
answers the coarse on-boundary CONDITION that perception, line-picking and the
sparse polygon all failed - setback VALUES still come from dimensions.

The boundary comes from vision (not the dash-dot convention). The mask is a
region hint, measured against a generous tolerance because image-gen resizes ~4%.

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_slice14
"""

import numpy as np
import fitz

from spikes.geometry_extraction.envelope import envelope_mask, fill_building_envelope
from spikes.geometry_extraction.viewports import (
    extract_viewports,
    label_viewports,
    locate_titles,
)
from spikes.geometry_extraction.vision import extract_site_regions, list_titles, render_sheet

SAMPLE_PDF = "assets/site_plan.pdf"
INPUT_PATH = "tmp/slice14_in.png"
COLOURED_PATH = "tmp/slice14_col.png"
ZOOM = 3.0
MM_PER_PT = 25.4 / 72 * 100
TOUCH_MM = 500  # within this of the boundary counts as touching (image-gen ~4% slack)


def main() -> None:
    page = fitz.open(SAMPLE_PDF)[0]
    rect = isolate_site_plan(page)

    wpx, hpx = fill_building_envelope(SAMPLE_PDF, 0, rect, COLOURED_PATH, INPUT_PATH, ZOOM)
    mask = envelope_mask(COLOURED_PATH, (wpx, hpx))

    regions = extract_site_regions(INPUT_PATH)  # boundary from vision, not linetype
    boundary = [(rect.x0 + v.x * rect.width, rect.y0 + v.y * rect.height)
                for v in regions.boundary_top_line]
    if len(boundary) < 2:
        print("no boundary from vision")
        return
    by = float(np.mean([p[1] for p in boundary]))
    bx0, bx1 = min(p[0] for p in boundary), max(p[0] for p in boundary)

    touching = 0
    total = 0
    print("north edge - does the building envelope reach the boundary?")
    prev = None
    for fx in np.linspace(0.03, 0.97, 60):
        px = int(fx * wpx)
        col = np.where(mask[:, px])[0]
        x = rect.x0 + fx * rect.width
        if len(col) == 0:
            band = "no building"
        else:
            total += 1
            gap = max(0.0, (rect.y0 + col.min() / hpx * rect.height - by) * MM_PER_PT)
            on = gap < TOUCH_MM
            touching += on
            band = "ON BOUNDARY" if on else "set back"
        if band != prev:
            print(f"  x={x:.0f}: {band}")
        prev = band

    pct = 100 * touching / total if total else 0
    print(f"\nbuilding touches north boundary along {pct:.0f}% of its built length")
    print("=> condition: " + ("on boundary for much of the north edge, recessed elsewhere"
                              if 15 < pct < 95 else
                              "on boundary" if pct >= 95 else "set back from boundary"))


def isolate_site_plan(page: fitz.Page) -> fitz.Rect:
    render_sheet(page, "tmp/slice14_sheet.png", max_width=4000)
    located = locate_titles(page, list_titles("tmp/slice14_sheet.png"))
    labelled = label_viewports(extract_viewports(page), located)
    site = next(vp for vp in labelled if vp.title and "site plan" in vp.title.lower())
    return fitz.Rect(site.x0, site.y0, site.x1, site.y1)


if __name__ == "__main__":
    main()
