from src.query.pipeline import run_query_pipeline
from src.query.schemas import LlmPlanningResponse
from src.query.cli import Cli
from src.planning.service import PlanningSource
from src.indexing.gemini_embedder import GeminiEmbedder
from src.indexing.chromadb import ChromaDb
from src.indexing.pipeline import run_indexing_pipeline
from src.llm.gemini_llm import GeminiLlm
import argparse


DB_COLLECTION_NAME = "planning"

# Planning scheme API filters
PLANNING_SCHEME = "Port Phillip"
MAX_RESULTS: int | None = None
KEY_WORD: str | None = None


def run_indexing(
    planning_scheme=PLANNING_SCHEME,
    collection=DB_COLLECTION_NAME,
    max_results=MAX_RESULTS,
    key_word=KEY_WORD,
):
    """Ingest, chunk, embedd and store Planning Scheme data"""

    source = PlanningSource(
        planning_scheme=planning_scheme,
        key_word=key_word,
        max_results=max_results,
    )
    embedder = GeminiEmbedder()
    store = ChromaDb(collection_name=collection)

    run_indexing_pipeline(source, embedder, store)


def run_query():
    ui = Cli()
    llm = GeminiLlm(schema=LlmPlanningResponse)
    embedder = GeminiEmbedder()
    store = ChromaDb(collection_name=DB_COLLECTION_NAME)

    run_query_pipeline(ui, llm, embedder, store)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=False)

    index = sub.add_parser(
        "index", help="Ingest, chunk, embedd and store Planning Scheme data"
    )
    index.add_argument(
        "--key-word",
        nargs="?",
        default=None,
        help="Only index clauses with title containing key word",
    )
    index.add_argument("--scheme", default=PLANNING_SCHEME)
    index.add_argument(
        "--max-results",
        type=int,
        help="Cap number of results returned from Planning Scheme API",
        default=MAX_RESULTS,
    )

    args = parser.parse_args()

    if args.command:
        run_indexing(
            planning_scheme=args.scheme,
            max_results=args.max_results,
            key_word=args.key_word,
        )
    else:
        run_query()
