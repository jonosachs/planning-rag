"""Generic query -> answer: select page -> retrieve controls -> read & compare.

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_assess "what is the site coverage and does it comply"
"""

import sys

from spikes.geometry_extraction.read_answer import assess_query

DRAWING_SET = [
    "assets/site_plan.pdf",
    "assets/elevations_and_sections.pdf",
    "assets/feature_survey.pdf",
]
DEFAULT_QUERY = "What is the site coverage and does it comply with the planning scheme?"


def main() -> None:
    query = " ".join(sys.argv[1:]).strip() or DEFAULT_QUERY
    selection, answer, invented = assess_query(query, DRAWING_SET)

    print(f"query: {query}\n")
    print("page(s):", ", ".join(f"{r.pdf} p.{r.page}" for r in selection.selections))
    print(f"values read: {answer.values_read}")
    if invented:
        print(f"  [!] not found in page text (possible hallucination): {invented}")
    verdict = {True: "COMPLIES", False: "DOES NOT COMPLY", None: "UNDETERMINED"}[answer.complies]
    print(f"verdict: {verdict}")
    print(f"reasoning: {answer.reasoning}")
    if answer.citations:
        print("citations: " + ", ".join(f"{c.ordinance_id} {c.title}" for c in answer.citations))


if __name__ == "__main__":
    main()
