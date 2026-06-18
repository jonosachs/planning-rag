import httpx
from dataclasses import dataclass

SCHEMES_URL = "https://api.app.planning.vic.gov.au/planning/v2/schemes/"
SCHEME_BASE_URL = "https://api.app.planning.vic.gov.au/planning/v2/ordinance/scheme/"


@dataclass
class ClauseRef:
    ordinance_id: str
    title: str
    semantic_number: str
    scheme_id: str


@dataclass
class ClauseDoc:
    clause_id: str
    scheme_id: str
    semantic_number: str
    gazettal_date: str
    amendment_number: str
    title: str
    content: str


def get_scheme_clauses(title: str, qty: int | None = None) -> list[ClauseDoc]:
    schemes = fetch_scheme_index()
    scheme_id = find_scheme_id_by_title(schemes, title)
    scheme_nav = fetch_scheme_nav(scheme_id)
    # Scheme payload holds nested tree of clauses in the 'nav' field
    scheme_nav_tree = scheme_nav["nav"]
    # Parse relevant clause fields as Clause objects
    normalised_clauses = flatten_clause_refs(scheme_id, scheme_nav_tree)

    if qty:
        normalised_clauses = normalised_clauses[:qty]

    docs = fetch_clause_documents(normalised_clauses)
    normalised_docs = parse_clause_docs(scheme_id, docs)
    return normalised_docs


def fetch_clause_documents(clause_refs: list[ClauseRef]) -> list[dict]:
    clause_docs = []

    for cr in clause_refs:
        clause_doc = fetch_a_clause_document(cr)
        clause_docs.append(clause_doc)

    return clause_docs


def fetch_a_clause_document(clause_ref: ClauseRef) -> dict:
    url = f"{SCHEME_BASE_URL}{clause_ref.scheme_id}/{clause_ref.semantic_number}"
    response = httpx.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_scheme_nav(scheme_id: str) -> dict:
    url = f"{SCHEME_BASE_URL}{scheme_id}/nav"
    response = httpx.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_scheme_index() -> list[dict]:
    url = SCHEMES_URL
    response = httpx.get(url, timeout=30)
    response.raise_for_status()
    # unpack list
    unpacked = response.json()
    return unpacked


def find_scheme_id_by_title(schemes: list[dict], target_title: str) -> str:
    for scheme in schemes:
        if scheme["title"] == target_title:
            return scheme["schemeID"]

    raise KeyError(f"{target_title} not found")


def flatten_clause_refs(
    scheme_id: str, clause_nodes: list[dict], normalised: list[ClauseRef] | None = None
) -> list[ClauseRef]:

    if normalised is None:
        normalised = []

    for cn in clause_nodes:
        clause_ref = build_clause_ref(cn, scheme_id)
        normalised.append(clause_ref)

        if cn.get("children"):
            flatten_clause_refs(scheme_id, cn.get("children"), normalised)

    return normalised


def parse_clause_docs(scheme_id: str, clause_docs: list[dict]) -> list[ClauseDoc]:
    clauses = []

    for c in clause_docs:
        clause = ClauseDoc(
            clause_id=c["id"],
            scheme_id=scheme_id,
            semantic_number=c["semanticNumber"],
            gazettal_date=c["gazettalDate"],
            amendment_number=c["amendmentNumber"],
            title=c["title"],
            content=c["content"],
        )
        clauses.append(clause)

    return clauses


def build_clause_ref(data, scheme_id) -> ClauseRef:
    clause_ref = ClauseRef(
        data["ordinanceID"],
        data["title"],
        data["semanticNumber"],
        scheme_id=scheme_id,
    )
    return clause_ref
