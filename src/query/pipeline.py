from src.indexing.interfaces import Embedder, VectorStore
from src.llm.interface import Llm
from src.query.interfaces import UserInterface
from src.query.parse import parse_search_results, select_cited
from src.query.prompt import build_llm_prompt


def run_query_pipeline(
    ui: UserInterface, llm: Llm, embedder: Embedder, store: VectorStore
):
    query = ui.get_user_query()
    embedded_query = embedder.embed_text(query)
    search_results = store.run_query(embedded_query)
    citations = parse_search_results(search_results)
    prompt = build_llm_prompt(query, citations)
    response = llm.get_response(prompt)
    cited = select_cited(response, citations)
    ui.show_cited_response(response.answer, cited)
