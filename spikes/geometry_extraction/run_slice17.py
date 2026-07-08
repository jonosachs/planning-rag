"""Slice 17: location-confirmed setbacks (certify + keep distinct instances).

The model identifies each setback with a position. Code pairs it to the nearest
dimension token on the sheet with the same value. That single step:
  - certifies the value by a REAL instance near where the model pointed
    (a coincidental match elsewhere won't be near, so it fails the guard), and
  - keeps equal-valued setbacks distinct - two 1030s at different points pair to
    two different tokens, so they stay two facts (no value-based dedup).
Two identified setbacks are the same fact only if they pair to the SAME token.

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_slice17
"""

import math

import fitz

from spikes.geometry_extraction.geometry import clip_geometry, extract_page_geometry
from spikes.geometry_extraction.viewports import (
    extract_viewports,
    label_viewports,
    locate_titles,
)
from spikes.geometry_extraction.vision import identify_setbacks, list_titles, render_sheet

SAMPLE_PDF = "assets/site_plan.pdf"
CROP_PATH = "tmp/slice17_crop.png"
NEAR_PT = 250  # a token must be within this of the model's point to certify by location


def main() -> None:
    page = fitz.open(SAMPLE_PDF)[0]
    rect = isolate_site_plan(page)
    site_geo = clip_geometry(extract_page_geometry(page), rect)
    tokens = [t for t in site_geo.text_tokens if t.text.strip().isdigit()]

    page.get_pixmap(matrix=fitz.Matrix(4, 4), clip=rect, alpha=False).save(CROP_PATH)
    identified = identify_setbacks(CROP_PATH)

    print(f"model identified {len(identified.setbacks)} setbacks; pairing to tokens:\n")
    used: dict[int, str] = {}  # token index -> first role/value that claimed it
    for s in identified.setbacks:
        mx = rect.x0 + s.x * rect.width
        my = rect.y0 + s.y * rect.height
        matches = [(i, t) for i, t in enumerate(tokens) if t.text.strip() == str(s.value_mm)]
        if not matches:
            print(f"  {s.role:<5} {s.value_mm:>6}mm  REJECTED (value not on sheet)")
            continue
        i, tok = min(matches, key=lambda it: math.dist(it[1].center, (mx, my)))
        dist = math.dist(tok.center, (mx, my))
        if dist > NEAR_PT:
            print(f"  {s.role:<5} {s.value_mm:>6}mm  WEAK (nearest token {dist:.0f}pt from model point)")
            continue
        dup = i in used
        used.setdefault(i, f"{s.role} {s.value_mm}")
        note = f"DUPLICATE of {used[i]}" if dup else f"token#{i} @({tok.center[0]:.0f},{tok.center[1]:.0f})"
        print(f"  {s.role:<5} {s.value_mm:>6}mm  CERTIFIED  {note}  [{s.status}]")

    distinct = len(used)
    print(f"\n{distinct} distinct certified setback instances")


def isolate_site_plan(page: fitz.Page) -> fitz.Rect:
    render_sheet(page, "tmp/slice17_sheet.png", max_width=4000)
    located = locate_titles(page, list_titles("tmp/slice17_sheet.png"))
    labelled = label_viewports(extract_viewports(page), located)
    site = next(vp for vp in labelled if vp.title and "site plan" in vp.title.lower())
    return fitz.Rect(site.x0, site.y0, site.x1, site.y1)


if __name__ == "__main__":
    main()
