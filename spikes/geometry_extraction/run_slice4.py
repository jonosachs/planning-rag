"""Slice 4: segment the sheet into viewports and describe each.

Prints every recovered viewport with the scale label(s), title words, and
dimension values that fall inside it - enough to see whether the drawings
separate cleanly and which one is the proposed site plan.

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_slice4
"""

import fitz

from spikes.geometry_extraction.geometry import extract_page_geometry
from spikes.geometry_extraction.viewports import extract_viewports

SAMPLE_PDF = "assets/site_plan.pdf"
TITLE_WORDS = {"site", "plan", "external", "works", "garden", "courtyard",
               "proposed", "elevation", "section", "floor", "roof", "landscape"}


def main() -> None:
    page = fitz.open(SAMPLE_PDF)[0]
    geo = extract_page_geometry(page)
    viewports = extract_viewports(page)
    print(f"{len(viewports)} viewports recovered\n")

    for i, rect in enumerate(sorted(viewports, key=lambda r: (round(r.y0), r.x0))):
        toks = [t for t in geo.text_tokens if rect.contains(fitz.Point(t.center))]
        scales = sorted({t.text for t in toks if t.text.startswith("1:")}
                        | scale_labels(toks))
        titles = [t.text for t in toks if t.text.strip().lower() in TITLE_WORDS]
        dims = sorted({int(t.text) for t in toks
                       if t.text.isdigit() and len(t.text) in (3, 4, 5)})
        print(f"[{i}] ({rect.x0:.0f},{rect.y0:.0f})-({rect.x1:.0f},{rect.y1:.0f}) "
              f"{rect.width:.0f}x{rect.height:.0f}")
        print(f"    scales={scales}  titles={titles[:8]}")
        print(f"    dims({len(dims)})={dims}\n")


def scale_labels(toks) -> set[str]:
    # catch "1", ":", "100" split across tokens near a 'scale' word
    joined = " ".join(t.text for t in toks)
    import re
    return {f"1:{m}" for m in re.findall(r"1\s*:\s*(\d{1,4})", joined)}


if __name__ == "__main__":
    main()
