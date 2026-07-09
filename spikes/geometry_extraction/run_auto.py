"""Auto-routed planning query: classify -> dispatch to the right pipeline.

Routes stated-value queries (site coverage, POS, permeability, height...) to the
generic read-and-compare, and geometric queries (per-boundary setbacks) to the
setback/height pipeline.

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_auto "what is the site coverage and does it comply"
    .venv/bin/python -m spikes.geometry_extraction.run_auto "do the setbacks comply"
"""

import sys

from spikes.geometry_extraction.compliance import assess_setback_compliance
from spikes.geometry_extraction.read_answer import assess_query
from spikes.geometry_extraction.vision import route_query

SITE_PLAN_PDF = "assets/site_plan.pdf"
DRAWING_SET = [
    "assets/site_plan.pdf",
    "assets/elevations_and_sections.pdf",
    "assets/feature_survey.pdf",
]
VERDICT = {True: "COMPLIES", False: "DOES NOT COMPLY", None: "UNDETERMINED"}


def main() -> None:
    query = " ".join(sys.argv[1:]).strip() or "Do the setbacks comply with the planning scheme?"
    route = route_query(query)
    print(f"query: {query}")
    print(f"route: {route.approach} - {route.reason}\n")

    if route.approach == "geometric":
        show_geometric(*assess_setback_compliance(SITE_PLAN_PDF, query))
    else:
        show_stated(*assess_query(query, DRAWING_SET))


def show_geometric(answer, response) -> None:
    print(f"drawing: {answer.drawing}; front = {answer.front_side} side")
    for f in response.findings:
        print(f"  {f.boundary}: {VERDICT[f.complies]} - {f.reasoning[:120]}")
    print(f"\noverall: {response.overall}")
    print("citations: " + ", ".join(f"{c.ordinance_id} {c.title}" for c in response.citations))


def show_stated(selection, answer, invented) -> None:
    print("page(s):", ", ".join(f"{r.pdf} p.{r.page}" for r in selection.selections))
    print(f"values read: {answer.values_read}")
    if invented:
        print(f"  [!] not found in page text: {invented}")
    print(f"verdict: {VERDICT[answer.complies]}")
    print(f"reasoning: {answer.reasoning}")
    print("citations: " + ", ".join(f"{c.ordinance_id} {c.title}" for c in answer.citations))


if __name__ == "__main__":
    main()
