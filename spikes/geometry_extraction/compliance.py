"""Link the setback pipeline to the RAG workflow for a compliance answer.

Extract validated setback facts (spike pipeline) -> retrieve the relevant
planning controls from the existing RAG index (src) -> LLM compares the facts to
the controls per boundary. Imports the app's RAG pieces; does not modify src.
"""

from pydantic import BaseModel

from src.indexing.chromadb import ChromaDb
from src.indexing.gemini_embedder import GeminiEmbedder
from src.llm.gemini_llm import GeminiLlm
from src.query.schemas import PlanningCitation

from spikes.geometry_extraction.pipeline import SetbackAnswer, answer_setbacks
from spikes.geometry_extraction.height import (
    HeightFacts,
    building_height_facts,
    required_setback_range_m,
    setback_verdict,
)

COLLECTION = "planning"
ELEVATIONS_PDF = "assets/elevations_and_sections.pdf"
SURVEY_PDF = "assets/feature_survey.pdf"
RETRIEVAL_SUFFIX = (
    " residential building street front, side and rear setback from boundary "
    "requirements and standards (metres)"
)

COMPLIANCE_PROMPT = """You are assessing whether a proposed building's setbacks
comply with the Victorian planning scheme. Use ONLY the planning controls in the
context - if the applicable control is not there, say you cannot determine.

Setbacks below are in millimetres or metres; controls are in metres - convert
before comparing. For each boundary give: the measured setback, the relevant
control, complies (true / false / null if undetermined), and reasoning. If a
setback is flagged for review or "on boundary", assess it accordingly (a wall on
the boundary is a nil setback). Cite the controls you rely on.

The facts include the building's overall HEIGHT and, for side/rear boundaries, a
code-computed required setback (from wall height and natural ground). Use the
overall height for any max-height control, and use the code-computed required
side/rear setbacks and their verdict (complies / does not comply / marginal).

User question: {query}

Extracted setback facts (validated against the drawing dimensions):
{facts}

Planning controls (retrieved):
{context}
"""


class SetbackFinding(BaseModel):
    boundary: str  # front / rear / side
    measured_setback: str  # e.g. "4400mm (4.4m), flagged existing"
    control: str  # the requirement relied on
    complies: bool | None  # null if it cannot be determined
    reasoning: str


class ComplianceResponse(BaseModel):
    findings: list[SetbackFinding]
    overall: str
    citations: list[PlanningCitation]


def assess_setback_compliance(pdf_path: str, query: str) -> tuple[SetbackAnswer, ComplianceResponse]:
    answer = answer_setbacks(pdf_path, query)
    height = building_height_facts(ELEVATIONS_PDF, SURVEY_PDF)
    context = retrieve_controls(query)
    prompt = COMPLIANCE_PROMPT.format(query=query, facts=format_facts(answer, height), context=context)
    response = GeminiLlm(schema=ComplianceResponse).get_response(prompt)
    return answer, response


def retrieve_controls(query: str, n_results: int = 8) -> str:
    embedded = GeminiEmbedder().embed_text(query + RETRIEVAL_SUFFIX)
    results = ChromaDb(collection_name=COLLECTION).run_query(embedded, n_results=n_results)
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    return "\n\n".join(
        f"[{(m or {}).get('ordinance_id', '?')} {(m or {}).get('title', '')}]\n{d}"
        for d, m in zip(docs, metas)
    )


def format_facts(answer: SetbackAnswer, height: HeightFacts) -> str:
    lines = [f"Drawing: {answer.drawing}; front boundary is the {answer.front_side} side."]
    if height.overall_height_m is not None:
        lines.append(
            f"Overall building height = {height.overall_height_m} m "
            f"(ridge RL {height.ridge_rl} - lowest natural ground RL {height.ground_min}, AHD)."
        )
    lines.append(
        f"Wall-top RL {height.wall_top_rl} AHD; natural ground per side (survey, AHD): "
        f"{height.ground}."
    )
    req = required_setback_range_m(height.wall_top_rl, height.ground_min, height.ground_max)
    for b in answer.boundaries:
        if b.on_boundary:
            base = f"{b.role} ({b.side}): building ON the boundary (nil / 0mm setback)"
        elif b.governing_mm is not None:
            provided_m = round(b.governing_mm / 1000, 3)
            base = f"{b.role} ({b.side}): {provided_m} m provided ({b.governing_reason})"
            if b.role in ("side", "rear") and req is not None:
                base += (f"; wall-height-based required setback {req[0]}-{req[1]} m "
                         f"-> {setback_verdict(provided_m, req)}")
        else:
            base = f"{b.role} ({b.side}): setback unresolved"
        recesses = [(v, s) for v, s in b.certified if v != b.governing_mm]
        if recesses:
            base += "; recessed at " + ", ".join(f"{v}mm[{s}]" for v, s in recesses)
        lines.append(f"- {base}")
    return "\n".join(lines)
