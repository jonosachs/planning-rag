"""Integration run: ask for setbacks, end to end.

Query -> model selects the relevant drawing -> per-boundary strip routine ->
governing setback per boundary. Prints the flow and checks the governing values
against the known answer for the sample sheet.

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_integration
"""

from spikes.geometry_extraction.pipeline import answer_setbacks

SAMPLE_PDF = "assets/site_plan.pdf"
QUERY = "What are the building setbacks from each property boundary?"
EXPECTED = {0, 1030, 4400, 10800}  # north on-boundary, south, front, rear


def main() -> None:
    answer = answer_setbacks(SAMPLE_PDF, QUERY)

    print(f"query: {answer.query}")
    print(f"selected drawing: {answer.drawing!r}")
    print(f"reason: {answer.drawing_reason}")
    print(f"front boundary: {answer.front_side} "
          f"(cue: {answer.street_cue}; confidence: {answer.front_confidence})\n")

    governing = set()
    for b in answer.boundaries:
        gov = "0mm (on boundary)" if b.on_boundary else (
            f"{b.governing_mm}mm ({b.governing_reason})" if b.governing_mm is not None else "UNRESOLVED"
        )
        flag = "  [model/envelope disagree]" if b.model_envelope_disagree else ""
        print(f"  {b.side} ({b.role}): {gov}{flag}")
        print(f"        certified: {b.certified or 'none'}   ignored: {b.ignored or 'none'}")
        if b.governing_mm is not None:
            governing.add(b.governing_mm)

    missing = EXPECTED - governing
    print(f"\ngoverning values found: {sorted(governing)}")
    print("PASS" if not missing else f"MISSING expected governing values: {sorted(missing)}")


if __name__ == "__main__":
    main()
