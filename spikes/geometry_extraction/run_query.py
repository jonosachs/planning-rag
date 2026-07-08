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
from spikes.geometry_extraction.vision import select_drawings

DRAWINGS = [
    "Proposed Site Plan - setbacks, site coverage, boundaries, private open space, site layout",
    "Elevations and Sections - building height, wall heights, roof form, RLs",
    "Feature Survey - existing/natural ground levels (AHD), site survey",
]
DEFAULT_QUERY = "What are the building setbacks from each boundary?"


def main() -> None:
    query = " ".join(sys.argv[1:]).strip() or DEFAULT_QUERY
    print(f"query: {query}\n")

    choice = select_drawings(query, DRAWINGS)
    print("1. relevant drawing(s) selected:")
    for title in choice.titles:
        print(f"   - {title}")
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
