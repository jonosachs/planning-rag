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

COLLECTION = "planning"
RETRIEVAL_SUFFIX = (
    " residential building street front, side and rear setback from boundary "
    "requirements and standards (metres)"
)

COMPLIANCE_PROMPT = """You are assessing whether a proposed building's setbacks
comply with the Victorian planning scheme. Use ONLY the planning controls in the
context - if the applicable control is not there, say you cannot determine.

Setbacks below are in millimetres; controls are usually in metres (4400mm = 4.4m)
- convert before comparing. For each boundary give: the measured setback, the
relevant control, complies (true / false / null if undetermined), and reasoning.
If a setback is flagged for review or "on boundary", assess it accordingly (a
wall on the boundary is a nil setback). Cite the controls you rely on.

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
    context = retrieve_controls(query)
    prompt = COMPLIANCE_PROMPT.format(query=query, facts=format_facts(answer), context=context)
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


def format_facts(answer: SetbackAnswer) -> str:
    lines = [f"Drawing: {answer.drawing}; front boundary is the {answer.front_side} side."]
    for b in answer.boundaries:
        if b.on_boundary:
            base = f"{b.role} ({b.side}): building ON the boundary (nil / 0mm setback)"
        elif b.governing_mm is not None:
            base = f"{b.role} ({b.side}): {b.governing_mm}mm ({b.governing_reason})"
        else:
            base = f"{b.role} ({b.side}): setback unresolved"
        recesses = [(v, s) for v, s in b.certified if v != b.governing_mm]
        if recesses:
            base += "; recessed at " + ", ".join(f"{v}mm[{s}]" for v, s in recesses)
        lines.append(f"- {base}")
    return "\n".join(lines)
