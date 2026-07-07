"""Slice 3: model selects which dimension answers the question; code measures.

Code builds fact-only dimension candidates (no meaning), the model selects the
one that answers the question and classifies it, then we guardrail-check that
the model echoed the code-measured value rather than inventing one.

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_slice3
"""

import fitz

from spikes.geometry_extraction.candidates import build_dimension_candidates
from spikes.geometry_extraction.geometry import extract_page_geometry
from spikes.geometry_extraction.vision import select_dimension

SAMPLE_PDF = "assets/site_plan.pdf"
SCALE = 100  # site-plan viewport; detail insets (1:50) would need per-region scale
QUESTION = "What is the setback of the building/courtyard from the north (title) boundary?"


def main() -> None:
    page = fitz.open(SAMPLE_PDF)[0]
    geo = extract_page_geometry(page)
    boundary = [s for s in geo.segments if s.is_dashed and s.length > 100]
    candidates = build_dimension_candidates(geo, SCALE, boundary)

    print(f"question: {QUESTION}")
    print(f"built {len(candidates)} dimension candidates\n")

    selection = select_dimension(QUESTION, candidates)
    chosen = next((c for c in candidates if c.id == selection.answer_candidate_id), None)

    print(f"selected: {selection.answer_candidate_id}  "
          f"classification: {selection.classification}")
    print(f"reason: {selection.reason}")
    if chosen is None:
        print("no candidate selected")
        return

    print(f"\nchosen candidate: annotated={chosen.annotated_value} "
          f"measured={chosen.measured_mm}mm nearby={chosen.nearby_labels}")
    ok = selection.value_mm == chosen.measured_mm
    print(f"guardrail (model echoed code value, not invented): "
          f"{'PASS' if ok else f'FAIL model={selection.value_mm} code={chosen.measured_mm}'}")


if __name__ == "__main__":
    main()
