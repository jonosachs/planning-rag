"""Ask whether the setbacks comply with the planning scheme (end to end).

Extract validated setbacks -> retrieve planning controls (RAG) -> compare.

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_compliance
"""

from spikes.geometry_extraction.compliance import assess_setback_compliance

SAMPLE_PDF = "assets/site_plan.pdf"
QUERY = "Do the proposed building setbacks comply with the planning scheme?"


def main() -> None:
    answer, response = assess_setback_compliance(SAMPLE_PDF, QUERY)

    print(f"query: {QUERY}")
    print(f"drawing: {answer.drawing}; front = {answer.front_side} side\n")

    print("setback compliance findings:")
    for f in response.findings:
        verdict = {True: "COMPLIES", False: "DOES NOT COMPLY", None: "UNDETERMINED"}[f.complies]
        print(f"  {f.boundary}: {verdict}")
        print(f"      measured: {f.measured_setback}")
        print(f"      control:  {f.control}")
        print(f"      reason:   {f.reasoning[:160]}")
    print(f"\noverall: {response.overall}")
    if response.citations:
        print("\ncitations:")
        for c in response.citations:
            print(f"  - {c.ordinance_id} {c.title}")


if __name__ == "__main__":
    main()
