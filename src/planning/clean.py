from bs4 import BeautifulSoup as bs
from src.planning.schemas import ClauseDoc, ClauseRef


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


def convert_html_to_text(content_html):
    soup = bs(content_html, "html.parser")
    content_text = soup.get_text(separator="\n", strip=True)
    return content_text


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
