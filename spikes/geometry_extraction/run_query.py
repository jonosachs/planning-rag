"""Manual integration test: type a query, watch the app narrow in.

Exercises the GENERIC "narrow to the relevant information" steps for any query:
  1. the model selects the relevant drawing from the drawing register,
  2. the RAG retrieves the relevant planning controls.
Deep geometric fact extraction is currently implemented for setbacks + building
height only; for those the full pipeline lives in run_integration / run_compliance.

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_query "What is the building height?"
    .venv/bin/python -m spikes.geometry_extraction.run_query "What is the site coverage?"
"""

import sys

from src.indexing.chromadb import ChromaDb
from src.indexing.gemini_embedder import GeminiEmbedder
from spikes.geometry_extraction.manifest import build_page_manifest, format_manifest
from spikes.geometry_extraction.vision import select_pages

DRAWING_SET = [
    "assets/site_plan.pdf",
    "assets/elevations_and_sections.pdf",
    "assets/feature_survey.pdf",
]
DEFAULT_QUERY = "What are the building setbacks from each boundary?"


def main() -> None:
    query = " ".join(sys.argv[1:]).strip() or DEFAULT_QUERY
    print(f"query: {query}\n")

    manifest = build_page_manifest(DRAWING_SET)
    choice = select_pages(query, format_manifest(manifest))
    print("1. page(s) selected (fuzzy-matched against the feature manifest):")
    for ref in choice.selections:
        print(f"   - {ref.pdf} p.{ref.page}")
    print(f"   reason: {choice.reason}\n")

    print("2. relevant planning controls (RAG):")
    for ordinance_id, title in retrieved_controls(query):
        print(f"   - {ordinance_id} {title}")

    print("\n3. extraction: geometric fact extraction is built for setbacks + building "
          "height (run_integration / run_compliance). Other controls narrow + retrieve "
          "here but don't yet have a bespoke extractor.")


def retrieved_controls(query: str, n: int = 6) -> list[tuple[str, str]]:
    embedded = GeminiEmbedder().embed_text(query)
    results = ChromaDb(collection_name="planning").run_query(embedded, n_results=n)
    metas = results.get("metadatas", [[]])[0]
    return [((m or {}).get("ordinance_id", "?"), (m or {}).get("title", "")) for m in metas]


if __name__ == "__main__":
    main()
