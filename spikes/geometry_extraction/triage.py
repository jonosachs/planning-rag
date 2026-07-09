"""Triage orchestrator: assess the control checklist, aggregate to a decision.

An "overall" query ("does the renovation comply?") can't be answered by one path.
This runs each applicable control through the right path (geometric setbacks/
height, or generic stated-value read), then aggregates: every control complies
with margin -> GREENLIGHT; any fail/undetermined -> SEND TO PLANNER (with the
items). Fail-closed: anything unresolved routes the whole project to a human.
"""

from dataclasses import dataclass

from spikes.geometry_extraction.compliance import assess_setback_compliance
from spikes.geometry_extraction.read_answer import assess_query

VERDICT = {True: "complies", False: "does not comply", None: "undetermined"}

# (control name, path, sub-query). Setbacks path also assesses building height.
CHECKLIST = [
    ("Setbacks & height", "geometric",
     "What are the building setbacks from each boundary and do they comply with the planning scheme?"),
    ("Site coverage", "stated",
     "What is the site coverage and does it comply with the planning scheme?"),
    ("Private open space", "stated",
     "What is the private open space provided and does it comply with the planning scheme?"),
    ("Permeability", "stated",
     "What is the site permeability and does it comply with the planning scheme?"),
]


@dataclass
class ControlResult:
    control: str
    verdict: str  # complies | does not comply | undetermined
    detail: str


def triage_project(drawing_set: list[str], site_plan_pdf: str) -> tuple[list[ControlResult], str]:
    results = []
    for name, path, sub_query in CHECKLIST:
        if path == "geometric":
            _, response = assess_setback_compliance(site_plan_pdf, sub_query)
            verdict, detail = reduce_setback(response)
        else:
            _, answer, _ = assess_query(sub_query, drawing_set)
            verdict, detail = VERDICT[answer.complies], answer.reasoning[:140]
        results.append(ControlResult(name, verdict, detail))

    greenlight = all(r.verdict == "complies" for r in results)
    return results, "GREENLIGHT" if greenlight else "SEND TO PLANNER"


def reduce_setback(response) -> tuple[str, str]:
    verdicts = [f.complies for f in response.findings]
    if any(v is False for v in verdicts):
        return "does not comply", response.overall
    if any(v is None for v in verdicts):
        return "undetermined", response.overall
    return "complies", response.overall
