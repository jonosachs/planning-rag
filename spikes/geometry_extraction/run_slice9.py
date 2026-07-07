"""Slice 9: one general primitive, two different question types.

Demonstrates that the same verify_feature primitive - with no setback knowledge -
handles both an element-classification question (does this dimension measure to
the dwelling?) and an on/offset condition question (is the dwelling on this
boundary?). The condition check is run twice to show temperature 0 makes it
stable, which is the fix for the earlier run-to-run flipping.

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_slice9
"""

import fitz

from spikes.geometry_extraction.candidates import build_dimension_candidates
from spikes.geometry_extraction.geometry import clip_geometry, extract_page_geometry
from spikes.geometry_extraction.viewports import (
    extract_viewports,
    label_viewports,
    locate_titles,
)
from spikes.geometry_extraction.verify import verify_feature
from spikes.geometry_extraction.vision import list_titles, render_sheet

SAMPLE_PDF = "assets/site_plan.pdf"

ELEMENT_Q = ("Does the red dimension measure a distance to the PROPOSED dwelling wall, "
             "or to an existing wall / fence / setout / other feature? "
             "holds = true only if it measures to the proposed dwelling.")
CONDITION_Q = ("Is the proposed dwelling built directly ON this red boundary line "
               "(touching it, zero setback) anywhere along it, or is it entirely set "
               "back from it? holds = true if any part of the dwelling sits on the boundary.")


def main() -> None:
    page = fitz.open(SAMPLE_PDF)[0]
    geo = extract_page_geometry(page)
    rect = isolate_site_plan(page)
    site_geo = clip_geometry(geo, rect)
    candidates = build_dimension_candidates(
        site_geo, 100, [s for s in site_geo.segments if s.is_dashed and s.length > 100])

    # Task A: element classification on the 9100 dimension
    c = next(c for c in candidates if c.annotated_value == 9100 and c.line)
    a = verify_feature(SAMPLE_PDF, 0, line_box(c.line), ELEMENT_Q, "tmp/verify_9100.png")
    print("TASK A - element classification (dim 9100):")
    print(f"  finding={a.finding[:80]!r} holds(dwelling)={a.holds} conf={a.confidence}\n")

    # Task B: on/offset condition on the north boundary - run twice for stability
    box = north_boundary_box(site_geo)
    print("TASK B - on/offset condition (north boundary), run twice @ temp 0:")
    for i in (1, 2):
        b = verify_feature(SAMPLE_PDF, 0, box, CONDITION_Q, f"tmp/verify_north_{i}.png")
        print(f"  run {i}: on_boundary={b.holds} conf={b.confidence} finding={b.finding[:70]!r}")


def line_box(line) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = line
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


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
    render_sheet(page, "tmp/slice9_sheet.png", max_width=4000)
    located = locate_titles(page, list_titles("tmp/slice9_sheet.png"))
    labelled = label_viewports(extract_viewports(page), located)
    site = next(vp for vp in labelled if vp.title and "site plan" in vp.title.lower())
    return fitz.Rect(site.x0, site.y0, site.x1, site.y1)


if __name__ == "__main__":
    main()
