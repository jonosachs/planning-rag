import httpx
from src.planning.schemas import ClauseRef

SCHEMES_BASE_URL = "https://api.app.planning.vic.gov.au/planning/v2/schemes/"


def fetch_schemes_index() -> list[dict]:
    url = SCHEMES_BASE_URL
    response = httpx.get(url, timeout=30)
    response.raise_for_status()
    # unpack list
    unpacked = response.json()
    return unpacked


def find_scheme_id_by_title(schemes: list[dict], target_title: str) -> str:
    for scheme in schemes:
        if scheme["title"] == target_title:
            print(
                f"✅ Found planning scheme for {target_title} with schemeID: {scheme['schemeID']}"
            )
            return scheme["schemeID"]

    raise KeyError(f"⚠️ {target_title} not found")


def fetch_scheme_payload(scheme_id: str) -> dict:
    url = f"{SCHEMES_BASE_URL}{scheme_id}"
    response = httpx.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def flatten_clause_nodes(clause_nodes: list[dict]) -> list[dict]:
    flattened = []
    child_keys = (
        "subClauses",
        "sections",
        "schedules",
        "ordinanceSections",
        "childOrdinances",
    )

    for node in clause_nodes:
        flat_node = {key: value for key, value in node.items() if key not in child_keys}
        flattened.append(flat_node)

        for key in child_keys:
            if node.get(key):
                flattened.extend(flatten_clause_nodes(node[key]))

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
