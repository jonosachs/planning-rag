from src.planning.ingest import (
    fetch_schemes_index,
    fetch_scheme_payload,
    find_scheme_id_by_title,
    flatten_clause_nodes,
    fetch_clause_payloads,
)
from src.planning.clean import (
    build_clause_refs,
    build_clause_docs,
    convert_html_to_text,
)
from src.planning.schemas import ClauseDoc, ClauseRef


def fetch_clause_refs(
    scheme: str, key_word: str | None = None, max_results: int | None = None
) -> list[ClauseRef]:
    # Get index of all scheme ids
    schemes = fetch_schemes_index()
    # Find the scheme id matching the user's target title
    scheme_id = find_scheme_id_by_title(schemes, scheme)
    # Fetch the scheme payload from the planning api using the id
    scheme_payload = fetch_scheme_payload(scheme_id)
    # Scheme payload holds nested clause refs: scheme->clauses->subClauses->sections
    clause_refs = scheme_payload["clauses"]
    # Flatten for easy iteration
    clause_refs = flatten_clause_nodes(clause_refs)

    print(f"ℹ️ Found {len(clause_refs)} clauses")

    # Filter by key words if provided
    if key_word:
        print(f"ℹ️ Filtering results for key word '{key_word}'")
        clause_refs = [
            node for node in clause_refs if key_word.lower() in node["title"].lower()
        ]

    # Trim number nodes to user max if specified
    if max_results:
        clause_refs = clause_refs[:max_results]
        print(f"✂️ Trimmed to {len(clause_refs)} results")

    # Convert clause references into ClauseRef objects
    clause_refs = build_clause_refs(scheme_id, clause_refs)

    return clause_refs


def parse_html(clause_docs: list[ClauseDoc]) -> list[ClauseDoc]:
    # Raw clause content is html. Covert it to text
    for c in clause_docs:
        if c.content:
            c.content = convert_html_to_text(c.content)

    return clause_docs


def run_fetch_scheme_pipeline(
    scheme, key_word=None, max_results=None
) -> list[ClauseDoc]:
    clause_refs = fetch_clause_refs(scheme, key_word, max_results)
    clause_payloads = fetch_clause_payloads(clause_refs)
    clause_docs = build_clause_docs(clause_payloads)
    cleaned = parse_html(clause_docs)
    return cleaned
