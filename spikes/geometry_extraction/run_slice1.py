"""Slice 1: validate the deterministic measurement engine (no LLM).

Thesis under test: once a feature is identified, measuring it off the vector
geometry at drawing scale reproduces the drafter's certified dimension.

We can't yet ask a model which segments are boundaries/walls (slice 2), so we
validate the engine differently: for each annotated dimension we measure the
segment its text sits on and compare span*scale to the certified value. Where
the scale is right and the segment is the true dimension line, the measurement
should match within a percent or two.

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_slice1
"""

import fitz

from spikes.geometry_extraction.geometry import extract_page_geometry
from spikes.geometry_extraction.measure import point_to_segment, points_to_mm

SAMPLE_PDF = "assets/site_plan.pdf"
ASSUMED_SCALE = 100  # the site plan viewport is 1:100; detail insets are 1:50
ON_LINE_TOL_PT = 3.0  # text must sit this close to count as "on" its dim line
PASS_TOL_PCT = 2.0


def main() -> None:
    page = fitz.open(SAMPLE_PDF)[0]
    geo = extract_page_geometry(page)
    print(
        f"{SAMPLE_PDF}: segments={len(geo.segments)} "
        f"tokens={len(geo.text_tokens)} scale_labels={geo.scale_labels}\n"
    )

    long_segs = [s for s in geo.segments if s.length > 15]
    rows = []
    for tok in geo.text_tokens:
        value = as_dimension(tok.text)
        if value is None:
            continue
        near = min(long_segs, key=lambda s: point_to_segment(tok.center, s))
        if point_to_segment(tok.center, near) > ON_LINE_TOL_PT:
            continue
        measured = points_to_mm(near.length, ASSUMED_SCALE)
        rows.append((value, measured))

    report(rows)


def as_dimension(text: str) -> int | None:
    text = text.strip()
    if text.isdigit() and 1000 <= int(text) <= 15000 and len(text) in (4, 5):
        return int(text)
    return None


def report(rows: list[tuple[int, float]]) -> None:
    print(f"annotated | measured@1:{ASSUMED_SCALE} |  err   | note")
    passed = 0
    for annotated, measured in rows:
        err = (measured - annotated) / annotated * 100
        note = ""
        if abs(err) <= PASS_TOL_PCT:
            passed += 1
        elif 95 <= err <= 105:
            note = "~2x: likely a 1:50 detail viewport"
        else:
            note = "gross: text matched the wrong segment"
        print(f"  {annotated:>6}  | {measured:9.0f}mm  | {err:+5.1f}% | {note}")
    print(f"\n{passed}/{len(rows)} within {PASS_TOL_PCT}% (correct scale + true dim line)")


if __name__ == "__main__":
    main()
