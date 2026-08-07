from src.planning.load import fetch_clause_payloads, fetch_clause_refs
from src.planning.parse import build_clause_docs
from src.planning.schemas import ClauseDoc


def run_load_scheme_pipeline(
    scheme: str, key_word: str | None = None, max_results: int | None = None
) -> list[ClauseDoc]:
    clause_refs = fetch_clause_refs(scheme, key_word, max_results)
    clause_payloads = fetch_clause_payloads(clause_refs)
    clause_docs = build_clause_docs(clause_payloads)
    return clause_docs
