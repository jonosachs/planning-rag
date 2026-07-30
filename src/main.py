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

# Planning constants
PLAN_SCHEME = "Port Phillip"
PLAN_KEY_WORD_FILTER = ["residential", "overshadow", "coverage", "height", ""]
PLAN_MAX_CLAUSES = 50  # excludes subclauses

DWGS_PATH = "assets/plans.pdf"


@dataclass
class IndexConfig:
    source: DataSource
    embedder: Embedder
    store: VectorStore


def run_planning_indexing(key_word=None):
    source = PlanningSource(
        planning_scheme=PLAN_SCHEME,
        key_word=key_word or PLAN_KEY_WORD_FILTER,
        max_results=PLAN_MAX_CLAUSES,
    )
    embedder = GeminiEmbedder()
    store = ChromaDb(collection_name="planning")

    run_indexing_pipeline(source, embedder, store)


def run_drawing_indexing():
    source = DrawingsSource(pdf_path=DWGS_PATH)
    embedder = GeminiEmbedder()
    store = ChromaDb(collection_name="drawings")

    run_indexing_pipeline(source, embedder, store)


def run_query():
    llm = GeminiLlm(schema=LlmPlanningResponse)
    embedder = GeminiEmbedder()
    store = ChromaDb(collection_name="planning")

    ui = Cli()
    query = ui.get_user_query()
    embedded_query = embedder.embed_text(query)
    query_context = store.run_query(embedded_query)
    prompt = package_prompt(query, query_context)

    response = llm.get_response(prompt)
    ui.show_cited_response(response)


# if __name__ == "__main__":
#     run_query()
