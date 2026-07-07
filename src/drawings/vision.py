from pathlib import Path
from pydantic import ValidationError

from src.drawings.ingest import extract_pages, get_planning_relevant_pages
from src.drawings.clean import render_pages
from src.drawings.pipeline import EXCLUDED_DWGS
from src.drawings.schemas import DrawingFactsResponse
from src.llm.gemini_llm import GeminiLlm


DEFAULT_DRAWING_FACTS_PATH = "tmp/drawing_facts.json"


DRAWING_FACT_EXTRACTION_PROMPT = """
You are reading architectural drawing pages for a Victorian planning assessment.

Extract structured drawing facts only. Do not assess planning compliance.
Use the attached page images as the source of truth and use visible text, dimensions,
linework, arrows, notes, title blocks, and existing/proposed graphics.

Focus on:
- project type and site address
- sheet number and sheet title
- existing/proposed/retained/demolished status
- front, side, and rear building setbacks
- dimensions from title boundaries to building walls
- walls on boundary, party walls, parapet walls, and existing boundary conditions
- whether a setback note applies to a building wall, roof/eave/gutter/downpipe,
  vent/chimney/solatube, awning, service, fence, or another element
- site area, site coverage, permeability, private open space, and building height
- zoning/schedule/overlay notes if visibly present

Rules:
- The page number fields in the JSON must be original PDF page numbers from the
  image manifest, not the sequential image order.
- Every DrawingPageFacts object must include the exact image_path from the
  manifest for that original PDF page.
- Every DrawingFact must repeat the same original_pdf_page and image_path as
  its parent page.
- Do not convert a roof/service/vent/chimney setback into a building wall setback.
- Do not call an unchanged existing condition proposed work.
- Preserve caveats where text is small, ambiguous, or machine-readable but not visually
  certain.
- Return facts with concise evidence strings copied or paraphrased from the drawings.
- Use confidence values: high, medium, or low.
"""


def extract_plan_facts(
    pdf_path: str,
    output_path: str = DEFAULT_DRAWING_FACTS_PATH,
    llm: GeminiLlm | None = None,
) -> DrawingFactsResponse:
    page_refs = render_relevant_plan_pages(pdf_path)
    image_paths = [ref["image_path"] for ref in page_refs]
    prompt = build_drawing_fact_extraction_prompt(page_refs)
    extractor = llm or GeminiLlm(schema=DrawingFactsResponse)
    facts = extractor.get_response(
        prompt,
        image_paths=image_paths,
    )
    write_drawing_facts(facts, output_path)
    return facts


def render_relevant_plan_pages(pdf_path: str) -> list[dict]:
    pages = extract_pages(pdf_path)
    relevant_pages = get_planning_relevant_pages(pages, EXCLUDED_DWGS)
    img_paths_by_page = render_pages(relevant_pages)
    return [
        {
            "original_pdf_page": page_number,
            "image_path": image_path,
        }
        for page_number, image_path in img_paths_by_page.items()
    ]


def build_drawing_fact_extraction_prompt(page_refs: list[dict]) -> str:
    manifest_lines = [
        "Image manifest. Use these exact original_pdf_page and image_path values in the JSON response:"
    ]
    manifest_lines.extend(
        (
            f"- original_pdf_page={ref['original_pdf_page']}; "
            f"image_path={ref['image_path']}"
        )
        for ref in page_refs
    )

    return f"{DRAWING_FACT_EXTRACTION_PROMPT}\n\n" + "\n".join(manifest_lines)


def write_drawing_facts(
    facts: DrawingFactsResponse,
    output_path: str = DEFAULT_DRAWING_FACTS_PATH,
) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(facts.model_dump_json(indent=2), encoding="utf-8")


def load_drawing_facts(
    path: str = DEFAULT_DRAWING_FACTS_PATH,
) -> DrawingFactsResponse | None:
    facts_path = Path(path)
    if not facts_path.exists():
        return None

    try:
        return DrawingFactsResponse.model_validate_json(
            facts_path.read_text(encoding="utf-8")
        )
    except ValidationError:
        print("⚠️ Cached drawing facts are stale; regenerate with --extract-drawing-facts")
        return None


def format_drawing_facts_for_prompt(
    facts: DrawingFactsResponse | None,
) -> str:
    if facts is None:
        return "No cached structured drawing facts found."

    lines = [
        "Cached structured drawing facts:",
        f"project_type: {facts.project_type}",
        f"site_address: {facts.site_address}",
    ]

    if facts.zoning_or_overlay_notes:
        lines.append("zoning_or_overlay_notes:")
        lines.extend(f"- {note}" for note in facts.zoning_or_overlay_notes)

    for page in facts.pages:
        lines.append(
            (
                f"Original PDF page {page.original_pdf_page} "
                f"image_path={page.image_path} "
                f"{page.sheet_number or ''} {page.sheet_title or ''}"
            ).strip()
        )
        for fact in page.facts:
            lines.append(
                " | ".join(
                    [
                        f"original_pdf_page={fact.original_pdf_page}",
                        f"image_path={fact.image_path}",
                        f"fact_type={fact.fact_type}",
                        f"value={fact.value}",
                        f"unit={fact.unit}",
                        f"element={fact.element}",
                        f"status={fact.status}",
                        f"evidence={fact.evidence}",
                        f"confidence={fact.confidence}",
                        f"caveat={fact.caveat}",
                    ]
                )
            )
        for note in page.notes:
            lines.append(f"note: {note}")

    if facts.overall_caveats:
        lines.append("overall_caveats:")
        lines.extend(f"- {caveat}" for caveat in facts.overall_caveats)

    return "\n".join(lines)
