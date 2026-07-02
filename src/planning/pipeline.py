def ingest_planning_data(
    scheme: str, key_word: str | None = None, max_results: int | None = None
) -> list[ClauseDoc]:
    # Get index of all scheme ids
    schemes = fetch_schemes_index()
    # Find the scheme id matching the user's target title
    scheme_id = find_scheme_id_by_title(schemes, scheme)
    # Fetch the scheme payload from the planning api using the id
    scheme_payload = fetch_scheme_payload(scheme_id)
    # Scheme payload holds nested clause refs: scheme->clauses->subClauses->sections
    clause_nodes = scheme_payload["clauses"]
    # Flatten for easy iteration
    clause_nodes = flatten_clause_nodes(clause_nodes)

    print(f"ℹ️ Found {len(clause_nodes)} clauses")

    # Filter by key words if provided
    if key_word:
        print(f"ℹ️ Filtering results for key word {key_word}")
        clause_nodes = [
            node for node in clause_nodes if key_word.lower() in node["title"].lower()
        ]
    # Trim number nodes to user max if specified
    if max_results:
        clause_nodes = clause_nodes[:max_results]
        print(f"✂️ Trimmed to {len(clause_nodes)} results")

    return clause_nodes


def clean(clause_nodes):
    # Convert clause references into ClauseRef objects
    clause_refs = build_clause_refs(scheme_id, clause_nodes)
    # Fetch the clause data
    clause_payloads = fetch_clause_payloads(clause_refs)
    # Convert clause data into ClauseDoc objects
    clause_docs = build_clause_docs(scheme_id, clause_payloads)

    # Raw clause content is html. Covert it to text
    for c in clause_docs:
        if c.content:
            c.content = convert_html_to_text(c.content)

    return clause_docs


def run_pipeline():
    ingest_planning_data()
    clean()
