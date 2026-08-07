import httpx
from src.planning.schemas import ClauseRef
from urllib.parse import urljoin
from src.planning.parse import build_clause_refs

SCHEMES_BASE_URL = "https://api.app.planning.vic.gov.au/planning/v2/schemes/"


def fetch_schemes_index() -> list[dict]:
    """Fetch the master index of all Victorian Planning schemes from the API"""

    url = SCHEMES_BASE_URL
    response = httpx.get(url, timeout=30)
    response.raise_for_status()
    # unpack list
    unpacked = response.json()
    return unpacked


def find_scheme_id_by_title(schemes: list[dict], target_title: str) -> str:
    """Walk the Planning schemes index and find a target scheme ID"""

    for scheme in schemes:
        # Title field contains canonical zone name in title case e.g."Bass Coast"
        if scheme["title"] == target_title:
            print(
                f"✅ Found planning scheme for {target_title} with schemeID: {scheme['schemeID']}"
            )
            return scheme["schemeID"]

    raise KeyError(f"⚠️ {target_title} not found")


def fetch_scheme_payload(scheme_id: str) -> dict:
    """Fetch a specific Planning scheme payload, including clause references tree, using the scheme ID"""

    url = urljoin(SCHEMES_BASE_URL, scheme_id)
    response = httpx.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def flatten_clause_ref_nodes(clause_nodes: list[dict]) -> list[dict]:
    """
    Flatten clause references tree for easier iteration
    Raw clause references looks like: clauses -> subClauses -> sections/schedules
    """

    flattened = []
    child_keys = (
        "subClauses",
        "sections",
        "schedules",
        "ordinanceSections",
        "childOrdinances",
    )

    for node in clause_nodes:
        # Get the highest level clause references (excluding any nested clauses)
        flat_node = {key: value for key, value in node.items() if key not in child_keys}
        flattened.append(flat_node)

        # Recursively add any nested sub-clause references as standalone entries
        # Parent info is contained in each clause playload
        for key in child_keys:
            if node.get(key):
                flattened.extend(flatten_clause_ref_nodes(node[key]))

    return flattened


def fetch_clause_payloads(clause_refs: list[ClauseRef]) -> list[dict]:
    clause_docs = []

    for ref in clause_refs:
        clause_header = f"{ref.title} {ref.ordinance_id}"
        try:
            clause_doc = fetch_a_clause_document(ref)
            clause_docs.append(clause_doc)
            print(f"✅ Fetched clause: {clause_header}")
        except httpx.HTTPStatusError as e:
            print(f"❌ Failed to fetch clause {clause_header}: {e}")
        except httpx.RequestError as e:
            print(f"❌ Request error fetching clause {clause_header}: {e}")

    if len(clause_docs) == 0:
        raise RuntimeError("⚠️ Failed to fetch any clauses")

    print(f"ℹ️ Obtained {len(clause_docs)} clauses")
    return clause_docs


def fetch_a_clause_document(clause_ref: ClauseRef) -> dict:
    url = (
        f"{SCHEMES_BASE_URL}{clause_ref.scheme_id}/ordinances/{clause_ref.ordinance_id}"
    )
    response = httpx.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


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
    clause_nodes = scheme_payload["clauses"]
    # Flatten for easy iteration
    clause_nodes = flatten_clause_ref_nodes(clause_nodes)

    print(f"ℹ️ Found {len(clause_nodes)} clauses")

    # Filter by key words if provided
    # TODO: Filter earlier in pipeline
    if key_word:
        print(f"ℹ️ Filtering results for key word '{key_word}'")
        clause_nodes = [
            node for node in clause_nodes if key_word.lower() in node["title"].lower()
        ]

    # Trim number nodes to user max if specified
    if max_results:
        clause_nodes = clause_nodes[:max_results]
        print(f"✂️ Trimmed to {len(clause_nodes)} results")

    # Convert to ClauseRef objects here so scheme_id never leaves this function -
    # each ref carries it from now on.
    return build_clause_refs(scheme_id, clause_nodes)
