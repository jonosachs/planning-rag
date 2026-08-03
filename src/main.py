from src.query.schemas import LlmPlanningResponse
from src.query.prompt import package_prompt
from src.query.cli import Cli
from src.planning.service import PlanningSource
from src.indexing.interfaces import DataSource, Embedder, VectorStore
from src.indexing.gemini_embedder import GeminiEmbedder
from src.indexing.chromadb import ChromaDb
from src.indexing.pipeline import run_indexing_pipeline
from src.llm.gemini_llm import GeminiLlm
from dataclasses import dataclass
import sys
import argparse


PLANNING_SCHEME = "Port Phillip"
DB_COLLECTION_NAME = "planning"
MAX_RESULTS = 100
KEY_WORDS = None  # Can be used to filter for specific clauses e.g. "overshadow"


@dataclass
class IndexConfig:
    source: DataSource
    embedder: Embedder
    store: VectorStore


def run_indexing(
    planning_scheme=PLANNING_SCHEME,
    collection=DB_COLLECTION_NAME,
    max_results=MAX_RESULTS,
    key_words=KEY_WORDS,
):
    jobs = [
        IndexConfig(
            source=PlanningSource(
                planning_scheme=planning_scheme,
                key_word=key_words,
                max_results=max_results,
            ),
            embedder=GeminiEmbedder(),
            store=ChromaDb(collection_name=collection),
        )
    ]
    for job in jobs:
        run_indexing_pipeline(job.source, job.embedder, job.store)


def run_query(collection=DB_COLLECTION_NAME):
    llm = GeminiLlm(schema=LlmPlanningResponse)
    embedder = GeminiEmbedder()
    store = ChromaDb(collection_name=collection)

    ui = Cli()
    query = ui.get_user_query()
    embedded_query = embedder.embed_text(query)
    query_context = store.run_query(embedded_query)
    prompt = package_prompt(query, query_context)

    response = llm.get_response(prompt)
    ui.show_cited_response(response)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", action="store_true", help="Index planning data")
    args = parser.parse_args()
    if args.index:
        run_indexing()
    else:
        run_query()
