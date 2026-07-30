"""Entry points for the planning-scheme RAG: seed a collection, or ask a question."""

import argparse

from src.query.schemas import LlmPlanningResponse
from src.query.prompt import package_prompt
from src.query.cli import Cli
from src.planning.service import PlanningSource
from src.indexing.gemini_embedder import GeminiEmbedder
from src.indexing.chromadb import ChromaDb
from src.drawings.service import DrawingsSource
from src.indexing.pipeline import run_indexing_pipeline
from src.llm.gemini_llm import GeminiLlm

# Planning constants
PLAN_SCHEME = "Port Phillip"
PLAN_KEY_WORD_FILTER = ["residential", "overshadow", "coverage", "height"]
PLAN_MAX_CLAUSES = 50  # excludes subclauses

DWGS_PATH = "assets/plans.pdf"

PLANNING_COLLECTION = "planning"
DRAWINGS_COLLECTION = "drawings"


def run_planning_indexing(key_words: list[str] | None = None) -> None:
    source = PlanningSource(
        planning_scheme=PLAN_SCHEME,
        key_words=key_words or PLAN_KEY_WORD_FILTER,
        max_results=PLAN_MAX_CLAUSES,
    )
    embedder = GeminiEmbedder()
    store = ChromaDb(collection_name=PLANNING_COLLECTION)

    run_indexing_pipeline(source, embedder, store)


def run_drawing_indexing() -> None:
    source = DrawingsSource(pdf_path=DWGS_PATH)
    embedder = GeminiEmbedder()
    store = ChromaDb(collection_name=DRAWINGS_COLLECTION)

    run_indexing_pipeline(source, embedder, store)


def run_query() -> None:
    llm = GeminiLlm(schema=LlmPlanningResponse)
    embedder = GeminiEmbedder()
    store = ChromaDb(collection_name=PLANNING_COLLECTION)

    ui = Cli()
    query = ui.get_user_query()
    embedded_query = embedder.embed_text(query)
    query_context = store.run_query(embedded_query)
    prompt = package_prompt(query, query_context)

    response = llm.get_response(prompt)
    ui.show_cited_response(response)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="planning-rag", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    index_planning = commands.add_parser(
        "index-planning", help=f"seed the '{PLANNING_COLLECTION}' collection"
    )
    index_planning.add_argument(
        "--keyword",
        action="append",
        dest="key_words",
        metavar="TERM",
        help=f"clause title filter, repeatable (default: {PLAN_KEY_WORD_FILTER})",
        default=None,
    )

    commands.add_parser(
        "index-drawings", help=f"seed the '{DRAWINGS_COLLECTION}' collection"
    )
    commands.add_parser("query", help="ask a planning question")

    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    if args.command == "index-planning":
        run_planning_indexing(args.key_words)
    elif args.command == "index-drawings":
        run_drawing_indexing()
    elif args.command == "query":
        run_query()


if __name__ == "__main__":
    main()
