from src.query.schemas import LlmPlanningResponse
from src.query.prompt import package_prompt
from src.query.cli import Cli
from src.planning.service import PlanningSource
from src.indexing.interfaces import DataSource, Embedder, VectorStore
from src.indexing.gemini_embedder import GeminiEmbedder
from src.indexing.chromadb import ChromaDb
from src.drawings.service import DrawingsSource
from src.indexing.pipeline import run_indexing_pipeline
from src.llm.gemini_llm import GeminiLlm
from dataclasses import dataclass


@dataclass
class IndexConfig:
    source: DataSource
    embedder: Embedder
    store: VectorStore


def run_indexing():
    jobs = [
        IndexConfig(
            source=PlanningSource(planning_scheme="Port Phillip"),
            embedder=GeminiEmbedder(),
            store=ChromaDb(collection_name="planning"),
        ),
        IndexConfig(
            source=DrawingsSource(pdf_path="assets/plans.pdf"),
            embedder=GeminiEmbedder(),
            store=ChromaDb(collection_name="planning"),
        ),
    ]
    for job in jobs:
        run_indexing_pipeline(job.source, job.embedder, job.store)


def run_query():
    llm = GeminiLlm(schema=LlmPlanningResponse)
    embedder = GeminiEmbedder()
    store = ChromaDb(collection_name="planning")

    run_indexing()

    ui = Cli()
    query = ui.get_user_query()
    embedded_query = embedder.embed_text(query)
    query_context = store.run_query(embedded_query)
    prompt = package_prompt(query, query_context)

    response = llm.get_response(prompt)
    ui.show_cited_response(response)


if __name__ == "__main__":
    run_query()
