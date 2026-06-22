import httpx
from bs4 import BeautifulSoup as bs
from dataclasses import dataclass

SCHEMES_BASE_URL = "https://api.app.planning.vic.gov.au/planning/v2/schemes/"


@dataclass
class ClauseRef:
    ordinance_id: str
    title: str
    scheme_id: str


@dataclass
class ClauseDoc:
    ordinance_id: str
    ordinance_type: str
    ordinance_level: str
    scheme_id: str
    gazettal_date: str
    amendment_number: str
    title: str
    content: str | None


def run_fetch_scheme_pipeline(
    scheme_title: str, key_word: str | None = None, max_results: int | None = None
) -> list[ClauseDoc]:
    # Get index of all scheme ids
    schemes = fetch_schemes_index()
    # Find the scheme id matching the user's target title
    scheme_id = find_scheme_id_by_title(schemes, scheme_title)
    # Fetch the scheme payload from the planning api using the id
    scheme_payload = fetch_scheme_payload(scheme_id)
    # Scheme payload holds nested clause refs: scheme->clauses->subClauses->sections
    clause_nodes = scheme_payload["clauses"]
    # Flatten for easy iteration
    clause_nodes_flat = flatten_clause_nodes(clause_nodes)

    print(f"ℹ️ Found {len(clause_nodes_flat)} clauses")

    # Trim number nodes to user max if specified
    if key_word:
        clause_nodes_flat = [
            node
            for node in clause_nodes_flat
            if key_word.lower() in node["title"].lower()
        ]
    if max_results:
        clause_nodes_flat = clause_nodes_flat[:max_results]
        print(f"✂️ Trimmed to {len(clause_nodes_flat)} results")

    # Convert clause references into ClauseRef objects
    clause_refs = build_clause_refs(scheme_id, clause_nodes_flat)
    # Fetch the clause data
    clause_payloads = fetch_clause_payloads(clause_refs)
    # Convert clause data into ClauseDoc objects
    clause_docs = build_clause_docs(scheme_id, clause_payloads)

    # Raw clause content is html. Covert it to text
    for c in clause_docs:
        if c.content:
            c.content = convert_html_to_text(c.content)

    return clause_docs


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


def build_clause_refs(scheme_id: str, clause_nodes: list[dict]) -> list[ClauseRef]:
    normalised = []

    for cn in clause_nodes:
        clause_ref = parse_as_clause_ref(cn, scheme_id)
        normalised.append(clause_ref)

    return normalised


def parse_as_clause_ref(data, scheme_id) -> ClauseRef:
    clause_ref = ClauseRef(
        data["ordinanceID"],
        data["title"],
        scheme_id=scheme_id,
    )
    return clause_ref


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


def convert_html_to_text(content_html):
    soup = bs(content_html, "html.parser")
    content_text = soup.get_text(separator="\n", strip=True)
    return content_text


def fetch_a_clause_document(clause_ref: ClauseRef) -> dict:
    url = (
        f"{SCHEMES_BASE_URL}{clause_ref.scheme_id}/ordinances/{clause_ref.ordinance_id}"
    )
    response = httpx.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def build_clause_docs(scheme_id: str, clause_docs: list[dict]) -> list[ClauseDoc]:
    clauses = []

    for c in clause_docs:
        clause = ClauseDoc(
            ordinance_id=c["ordinanceID"],
            ordinance_type=c["ordinanceType"],
            ordinance_level=c["ordinanceLevel"],
            scheme_id=scheme_id,
            gazettal_date=c["gazettalDate"],
            amendment_number=c["amendmentNumber"],
            title=c["title"],
            content=c.get("content"),
        )
        clauses.append(clause)

    return clauses
