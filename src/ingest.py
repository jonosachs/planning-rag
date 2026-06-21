import httpx
from bs4 import BeautifulSoup as bs
from dataclasses import asdict, dataclass

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


def run_fetch_scheme_pipeline(scheme_title: str) -> list[ClauseDoc]:
    schemes = fetch_schemes_index()
    scheme_id = find_scheme_id_by_title(schemes, scheme_title)
    scheme_payload = fetch_scheme_payload(scheme_id)
    # Scheme payload holds nested tree of clauses in the 'nav' field
    clause_nodes = scheme_payload["nav"]
    clause_refs = build_clause_refs(scheme_id, clause_nodes)
    clause_payloads = fetch_clause_payloads(clause_refs)
    clause_docs = build_clause_docs(scheme_id, clause_payloads)

    # Raw content is html. Covert it to string
    for c in clause_docs:
        c.content = normalise_content(c.content)

    return clause_docs


def normalise_content(content_html):
    soup = bs(content_html, "html.parser")
    content_string = soup.get_text(separator="\n", strip=True)
    return content_string


def fetch_clause_payloads(clause_refs: list[ClauseRef]) -> list[dict]:
    clause_docs = []

    for cr in clause_refs:
        try:
            clause_doc = fetch_a_clause_document(cr)
            clause_docs.append(clause_doc)
        except httpx.HTTPStatusError as e:
            print(f"Failed to fetch clause {asdict(cr)}: {e}")
        except httpx.RequestError as e:
            print(f"Request error fetching clause {asdict(cr)}: {e}")

    if len(clause_docs) == 0:
        raise RuntimeError("Failed to fetch any clauses")

    print(f"Obtained {len(clause_docs)} clauses")
    return clause_docs


def fetch_a_clause_document(clause_ref: ClauseRef) -> dict:
    url = f"{SCHEME_BASE_URL}{clause_ref.scheme_id}/{clause_ref.semantic_number}"
    response = httpx.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_scheme_payload(scheme_id: str) -> dict:
    url = f"{SCHEME_BASE_URL}{scheme_id}/nav"
    response = httpx.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_schemes_index() -> list[dict]:
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


def build_clause_refs(
    scheme_id: str, clause_nodes: list[dict], normalised: list[ClauseRef] | None = None
) -> list[ClauseRef]:

    if normalised is None:
        normalised = []

    for cn in clause_nodes:
        clause_ref = parse_as_clause_ref(cn, scheme_id)
        normalised.append(clause_ref)

        if cn.get("children"):
            build_clause_refs(scheme_id, cn.get("children"), normalised)

    return normalised


def build_clause_docs(scheme_id: str, clause_docs: list[dict]) -> list[ClauseDoc]:
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


def parse_as_clause_ref(data, scheme_id) -> ClauseRef:
    clause_ref = ClauseRef(
        data["ordinanceID"],
        data["title"],
        data["semanticNumber"],
        scheme_id=scheme_id,
    )
    return clause_ref
