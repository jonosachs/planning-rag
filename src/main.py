import argparse
import re
from dataclasses import dataclass

import fitz

from src.query.schemas import LlmComplianceResponse
from src.query.prompt import package_compliance_prompt
from src.query.cli import Cli
from src.planning.service import PlanningSource
from src.indexing.interfaces import DataSource, Embedder, VectorStore
from src.indexing.gemini_embedder import GeminiEmbedder
from src.indexing.chromadb import ChromaDb
from src.drawings.service import DrawingsSource
from src.drawings.evidence import (
    extract_visual_evidence,
    format_visual_evidence_for_prompt,
)
from src.drawings.proximity import extract_dimension_proximity_evidence
from src.drawings.vision import (
    DEFAULT_DRAWING_FACTS_PATH,
    extract_plan_facts,
    format_drawing_facts_for_prompt,
    load_drawing_facts,
)
from src.indexing.pipeline import run_indexing_pipeline
from src.llm.gemini_llm import GeminiLlm


PLANNING_COLLECTION = "planning"
DRAWINGS_COLLECTION = "drawings"
PLANNING_SCHEME = "Port Phillip"
DRAWINGS_PDF_PATH = "assets/plans.pdf"
MAX_DRAWING_IMAGES = 5
MAX_PLANNING_PARENT_CLAUSES = 5
PLANNING_RETRIEVAL_RESULTS = 30
DRAWING_RETRIEVAL_RESULTS = 10
SETBACK_QUERY_TERMS = ("setback", "setbacks", "boundary", "front", "side", "rear")
DIMENSION_PROXIMITY_QUERY_TERMS = (
    "setback",
    "setbacks",
    "boundary",
    "dimension",
    "dimensions",
    "distance",
    "offset",
    "front",
    "side",
    "rear",
)
CONTEXTUAL_DRAWING_TERMS = (
    "site statistics",
    "total site area",
    "existing g.f.a",
    "proposed new g.f.a",
)
SERVICE_SETBACK_TERMS = (
    "subfloor vent",
    "vent chimneys",
    "chimney",
    "solatube",
    "gutter",
    "downpipe",
    "dp-",
    "roofed awning",
    "roof",
    "service",
)
EXISTING_BOUNDARY_TERMS = (
    "existing wall on boundary",
    "existing party wall",
    "existing parapet wall",
    "edge of existing wall",
)
SINGLE_DWELLING_TERMS = (
    "single storey",
    "house",
    "dwelling",
    "existing front fence",
    "new works not visible",
    "replacing like for like",
)
MULTI_DWELLING_TERMS = (
    "two or more dwellings",
    "residential building",
    "apartment",
    "four to six storeys",
)
SINGLE_DWELLING_PLANNING_PREFIXES = ("54.", "32.")
SINGLE_DWELLING_EXCLUDED_PLANNING_PREFIXES = ("55.", "57.", "58.")


@dataclass
class IndexConfig:
    source: DataSource
    embedder: Embedder
    store: VectorStore


def run_indexing():
    embedder = GeminiEmbedder()
    jobs = [
        IndexConfig(
            source=PlanningSource(planning_scheme=PLANNING_SCHEME),
            embedder=embedder,
            store=ChromaDb(collection_name=PLANNING_COLLECTION),
        ),
        IndexConfig(
            source=DrawingsSource(pdf_path=DRAWINGS_PDF_PATH),
            embedder=embedder,
            store=ChromaDb(collection_name=DRAWINGS_COLLECTION),
        ),
    ]
    for job in jobs:
        run_indexing_pipeline(job.source, job.embedder, job.store)


def run_query(user_query: str | None = None, show_evidence: bool = False):
    ui = Cli()
    query = user_query or ui.get_user_query()

    llm = GeminiLlm(schema=LlmComplianceResponse)
    embedder = GeminiEmbedder()
    planning_store = ChromaDb(collection_name=PLANNING_COLLECTION)
    drawings_store = ChromaDb(collection_name=DRAWINGS_COLLECTION)

    embedded_query = embedder.embed_text(query)

    planning_results = planning_store.run_query(
        embedded_query,
        n_results=PLANNING_RETRIEVAL_RESULTS,
    )
    drawing_results = drawings_store.run_query(
        embedded_query,
        n_results=DRAWING_RETRIEVAL_RESULTS,
    )

    drawing_context = format_query_results(DRAWINGS_COLLECTION, drawing_results)
    drawing_image_paths = select_drawing_image_paths(
        query,
        drawings_store,
        drawing_results,
        max_images=MAX_DRAWING_IMAGES,
    )
    drawing_page_text = extract_selected_drawing_page_text(
        DRAWINGS_PDF_PATH,
        drawing_image_paths,
    )
    dimension_proximity_context = extract_query_dimension_proximity_evidence(
        query,
        DRAWINGS_PDF_PATH,
        drawing_image_paths,
    )
    drawing_interpretation = interpret_selected_drawing_page_text(
        DRAWINGS_PDF_PATH,
        drawing_image_paths,
    )
    cached_drawing_facts = format_drawing_facts_for_prompt(load_drawing_facts())
    visual_evidence_context = format_visual_evidence_for_prompt(
        extract_visual_evidence(
            query,
            drawing_image_paths,
            "\n\n".join(
                [
                    drawing_context,
                    cached_drawing_facts,
                    dimension_proximity_context,
                    drawing_interpretation,
                    drawing_page_text,
                ]
            ),
        )
    )
    if show_evidence:
        print(f"\n{dimension_proximity_context}\n")
        print(f"\n{visual_evidence_context}\n")
    development_context = infer_development_context(drawing_page_text)
    planning_context = format_expanded_planning_results(
        planning_store,
        planning_results,
        max_parent_clauses=MAX_PLANNING_PARENT_CLAUSES,
        development_context=development_context,
    )
    drawing_context = (
        f"{drawing_context}\n\n"
        f"{visual_evidence_context}\n\n"
        f"{cached_drawing_facts}\n\n"
        f"{dimension_proximity_context}\n\n"
        f"{drawing_interpretation}\n\n"
        f"{drawing_page_text}"
    )
    prompt = package_compliance_prompt(query, planning_context, drawing_context)

    response = llm.get_response(prompt, image_paths=drawing_image_paths)
    ui.show_cited_response(response)


def format_query_results(collection_name: str, results: dict) -> str:
    documents = first_result_list(results, "documents")
    metadatas = first_result_list(results, "metadatas")
    distances = first_result_list(results, "distances")

    if not documents:
        return f"No retrieved context from {collection_name}."

    context_items = []
    for index, document in enumerate(documents):
        metadata = metadatas[index] if index < len(metadatas) else {}
        distance = distances[index] if index < len(distances) else None
        context_items.append(
            "\n".join(
                [
                    f"{index + 1}. collection: {collection_name}",
                    f"distance: {distance}",
                    f"text: {document}",
                    f"metadata: {metadata}",
                ]
            )
        )

    return "\n\n".join(context_items)


def format_expanded_planning_results(
    store: ChromaDb,
    results: dict,
    max_parent_clauses: int,
    development_context: str | None = None,
) -> str:
    selected_ordinances = select_retrieved_ordinance_ids(
        results,
        max_parent_clauses,
        development_context=development_context,
    )
    if not selected_ordinances:
        return "No retrieved context from planning."

    records = store.get_all()
    documents = records.get("documents", [])
    metadatas = records.get("metadatas", [])
    chunks_by_ordinance = group_planning_chunks_by_ordinance(documents, metadatas)

    context_items = []
    for index, ordinance_id in enumerate(selected_ordinances):
        clause_chunks = chunks_by_ordinance.get(ordinance_id, [])
        if not clause_chunks:
            continue

        first_metadata = clause_chunks[0][1]
        chunk_text = "\n\n".join(
            format_expanded_planning_chunk(document, metadata)
            for document, metadata in clause_chunks
        )
        context_items.append(
            "\n".join(
                [
                    f"{index + 1}. expanded planning clause",
                    f"title: {first_metadata.get('title')}",
                    f"ordinance_id: {ordinance_id}",
                    f"scheme_id: {first_metadata.get('scheme_id')}",
                    chunk_text,
                ]
            )
        )

    if not context_items:
        return "No retrieved context from planning."

    return "\n\n".join(
        [
            format_planning_applicability_note(development_context),
            *context_items,
        ]
    )


def select_retrieved_ordinance_ids(
    results: dict,
    max_parent_clauses: int,
    development_context: str | None = None,
) -> list[str]:
    ordinance_ids = []

    for metadata in first_result_list(results, "metadatas"):
        if not is_applicable_planning_metadata(metadata, development_context):
            continue

        ordinance_id = metadata.get("ordinance_id")
        if ordinance_id and ordinance_id not in ordinance_ids:
            ordinance_ids.append(ordinance_id)

        if len(ordinance_ids) == max_parent_clauses:
            break

    return ordinance_ids


def is_applicable_planning_metadata(
    metadata: dict,
    development_context: str | None,
) -> bool:
    if development_context != "single_dwelling_renovation":
        return True

    title = metadata.get("title", "")

    if title.startswith(SINGLE_DWELLING_EXCLUDED_PLANNING_PREFIXES):
        return False

    return title.startswith(SINGLE_DWELLING_PLANNING_PREFIXES)


def format_planning_applicability_note(development_context: str | None) -> str:
    if development_context == "single_dwelling_renovation":
        return (
            "Planning applicability note: selected drawing pages indicate a "
            "single dwelling renovation/alteration context. Prefer Clause 54 "
            "single-dwelling controls and relevant zone/schedule controls. Do "
            "not apply Clause 55, 57, or 58 controls unless the drawings or user "
            "query identify two or more dwellings, a residential building, or a "
            "4-6 storey/apartment development."
        )

    return (
        "Planning applicability note: development type could not be confidently "
        "inferred from the selected drawing pages, so retrieved planning controls "
        "are not filtered by development type."
    )


def group_planning_chunks_by_ordinance(
    documents: list[str],
    metadatas: list[dict],
) -> dict[str, list[tuple[str, dict]]]:
    chunks_by_ordinance = {}

    for document, metadata in zip(documents, metadatas):
        ordinance_id = metadata.get("ordinance_id")
        if not ordinance_id:
            continue

        chunks_by_ordinance.setdefault(ordinance_id, []).append((document, metadata))

    for chunks in chunks_by_ordinance.values():
        chunks.sort(key=lambda item: item[1].get("chunk_index", 0))

    return chunks_by_ordinance


def format_expanded_planning_chunk(document: str, metadata: dict) -> str:
    return "\n".join(
        [
            f"chunk_index: {metadata.get('chunk_index')}",
            f"text: {document}",
            f"metadata: {metadata}",
        ]
    )


def first_result_list(results: dict, key: str) -> list:
    values = results.get(key) or []
    if not values:
        return []
    return values[0] or []


def extract_image_paths(results: dict, max_images: int) -> list[str]:
    image_paths = []

    for metadata in first_result_list(results, "metadatas"):
        image_path = metadata.get("img_path")
        if image_path and image_path not in image_paths:
            image_paths.append(image_path)

        if len(image_paths) == max_images:
            break

    return image_paths


def select_drawing_image_paths(
    query: str,
    store: ChromaDb,
    results: dict,
    max_images: int,
) -> list[str]:
    retrieved_paths = extract_image_paths(results, max_images)
    contextual_paths = find_contextual_drawing_image_paths(query, store)

    image_paths = []
    if retrieved_paths:
        image_paths.append(retrieved_paths[0])

    append_unique(image_paths, contextual_paths, max_images)
    append_unique(image_paths, retrieved_paths[1:], max_images)

    return image_paths


def find_contextual_drawing_image_paths(query: str, store: ChromaDb) -> list[str]:
    if not is_setback_query(query):
        return []

    records = store.get_all()
    paths = []

    for document, metadata in zip(
        records.get("documents", []),
        records.get("metadatas", []),
    ):
        if metadata.get("chunk_kind") != "page_summary":
            continue

        if has_contextual_drawing_terms(document):
            image_path = metadata.get("img_path")
            if image_path and image_path not in paths:
                paths.append(image_path)

    return paths


def is_setback_query(query: str) -> bool:
    lowered = query.lower()
    return any(term in lowered for term in SETBACK_QUERY_TERMS)


def is_dimension_proximity_query(query: str) -> bool:
    lowered = query.lower()
    return any(term in lowered for term in DIMENSION_PROXIMITY_QUERY_TERMS)


def extract_query_dimension_proximity_evidence(
    query: str,
    pdf_path: str,
    image_paths: list[str],
) -> str:
    if not is_dimension_proximity_query(query):
        return "No dimension proximity evidence requested for this query."

    return extract_dimension_proximity_evidence(pdf_path, image_paths)


def has_contextual_drawing_terms(document: str) -> bool:
    lowered = document.lower()
    return any(term in lowered for term in CONTEXTUAL_DRAWING_TERMS)


def append_unique(target: list[str], items: list[str], max_items: int) -> None:
    for item in items:
        if item not in target:
            target.append(item)

        if len(target) == max_items:
            return


def extract_selected_drawing_page_text(pdf_path: str, image_paths: list[str]) -> str:
    page_numbers = extract_page_numbers_from_image_paths(image_paths)
    if not page_numbers:
        return "No selected drawing page text."

    document = fitz.open(pdf_path)
    page_texts = []

    for page_number in page_numbers:
        page_index = page_number - 1
        if page_index < 0 or page_index >= len(document):
            continue

        text = normalise_page_text(document[page_index].get_text())
        page_texts.append(
            "\n".join(
                [
                    f"Selected drawing page {page_number} full PDF text:",
                    text,
                ]
            )
        )

    if not page_texts:
        return "No selected drawing page text."

    return "\n\n".join(page_texts)


def extract_page_numbers_from_image_paths(image_paths: list[str]) -> list[int]:
    page_numbers = []

    for image_path in image_paths:
        match = re.search(r"p(\d+)\.png$", image_path)
        if not match:
            continue

        page_number = int(match.group(1))
        if page_number not in page_numbers:
            page_numbers.append(page_number)

    return page_numbers


def normalise_page_text(text: str) -> str:
    return " ".join(text.split())


def infer_development_context(drawing_page_text: str) -> str | None:
    lowered = drawing_page_text.lower()

    if any(term in lowered for term in MULTI_DWELLING_TERMS):
        return None

    if any(term in lowered for term in SINGLE_DWELLING_TERMS):
        return "single_dwelling_renovation"

    return None


def interpret_selected_drawing_page_text(pdf_path: str, image_paths: list[str]) -> str:
    page_numbers = extract_page_numbers_from_image_paths(image_paths)
    if not page_numbers:
        return "No interpreted drawing notes."

    document = fitz.open(pdf_path)
    notes = []

    for page_number in page_numbers:
        page_index = page_number - 1
        if page_index < 0 or page_index >= len(document):
            continue

        text = normalise_page_text(document[page_index].get_text()).lower()
        notes.extend(interpret_service_setbacks(page_number, text))
        notes.extend(interpret_existing_boundary_conditions(page_number, text))

    if not notes:
        return "No interpreted drawing notes."

    return "Interpreted drawing notes:\n" + "\n".join(f"- {note}" for note in notes)


def interpret_service_setbacks(page_number: int, text: str) -> list[str]:
    notes = []

    for match in re.finditer(r"setback\s+\d+(?:\.\d+)?\s*mm\s+from\s+boundary", text):
        snippet = extract_text_window(text, match.start(), match.end(), window=220)
        if any(term in snippet for term in SERVICE_SETBACK_TERMS):
            notes.append(
                "Page "
                f"{page_number}: '{match.group(0)}' appears in a roof/service "
                "context, not a building wall setback. Nearby text: "
                f"{snippet}"
            )
        elif any(term in snippet for term in EXISTING_BOUNDARY_TERMS):
            notes.append(
                "Page "
                f"{page_number}: '{match.group(0)}' appears near existing-wall "
                "context, so do not assume it is a proposed building setback. "
                f"Nearby text: {snippet}"
            )

    return notes


def interpret_existing_boundary_conditions(page_number: int, text: str) -> list[str]:
    notes = []

    for term in EXISTING_BOUNDARY_TERMS:
        index = text.find(term)
        if index == -1:
            continue

        notes.append(
            f"Page {page_number}: existing boundary condition detected: "
            f"{extract_text_window(text, index, index + len(term), window=140)}"
        )

    return notes


def extract_text_window(text: str, start: int, end: int, window: int) -> str:
    return text[max(0, start - window) : min(len(text), end + window)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Index the planning scheme and drawings before querying.",
    )
    parser.add_argument(
        "-q",
        "--query",
        help="Run a single query without opening the interactive prompt.",
    )
    parser.add_argument(
        "--extract-drawing-facts",
        action="store_true",
        help=(
            "Use Gemini vision to extract structured facts from the plans PDF "
            f"and write {DEFAULT_DRAWING_FACTS_PATH}."
        ),
    )
    parser.add_argument(
        "--show-evidence",
        action="store_true",
        help="Print query-specific visual drawing evidence before the final answer.",
    )
    args = parser.parse_args()

    if args.seed:
        run_indexing()

    if args.extract_drawing_facts:
        extract_plan_facts(DRAWINGS_PDF_PATH)
        if not args.query:
            return

    run_query(args.query, show_evidence=args.show_evidence)


if __name__ == "__main__":
    main()
