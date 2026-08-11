from bs4 import BeautifulSoup as bs
from src.planning.schemas import ClauseDoc, ClauseRef


def build_clause_docs(clause_payloads: list[dict]) -> list[ClauseDoc]:
    clause_docs = []

    for cp in clause_payloads:
        scheme_id = cp["planningScheme"]["schemeID"]
        clause = ClauseDoc(
            ordinance_id=cp["ordinanceID"],
            ordinance_type=cp["ordinanceType"],
            ordinance_level=cp["ordinanceLevel"],
            scheme_id=scheme_id,
            semantic_num=cp["semanticNumber"],
            gazettal_date=cp["gazettalDate"],
            amendment_number=cp["amendmentNumber"],
            title=cp["title"],
            content=convert_html_to_text(cp.get("content")),
            section=cp.get("section", ""),
            parent_ordinance_id=cp.get("parentOrdinance", {}).get("ordinanceID"),
            parent_title=cp.get("parentOrdinance", {}).get("title"),
        )
        clause_docs.append(clause)

    return clause_docs


def convert_html_to_text(html) -> str:
    soup = bs(html, "html.parser")
    text = soup.get_text(separator="\n", strip=True)
    return text


def build_clause_refs(scheme_id: str, clause_nodes: list[dict]) -> list[ClauseRef]:
    clause_refs = []

    for node in clause_nodes:
        ref = ClauseRef(
            ordinance_id=node["ordinanceID"],
            title=node["title"],
            section=node.get("section", ""),
            scheme_id=scheme_id,
        )
        clause_refs.append(ref)

    return clause_refs
