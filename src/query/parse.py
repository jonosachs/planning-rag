from src.query.schemas import PlanningCitation, LlmPlanningResponse


def parse_search_results(search_results: dict) -> list[PlanningCitation]:
    """Parse vector db search results as PlanningCitation models"""

    ids = search_results["ids"][0]
    metadatas = search_results["metadatas"][0]
    documents = search_results["documents"][0]

    citations = []
    for i, record in enumerate(metadatas):
        c = PlanningCitation(
            citation_index=i,  # 0-based indexing
            citation_id=ids[i],
            scheme_id=record.get("scheme_id"),
            ordinance_id=record.get("ordinance_id"),
            semantic_num=record.get("semantic_num"),
            section=record.get("section", ""),
            chunk_index=record.get("chunk_index"),
            parent_title=record.get("parent_title", ""),
            title=record.get("title"),
            content=documents[i],
        )
        citations.append(c)

    return citations


def select_cited(
    response: LlmPlanningResponse, citations: list[PlanningCitation]
) -> dict[str, list[PlanningCitation]]:
    if not response.citation_idxs:
        return {}

    cited = [c for c in citations if c.citation_index in response.citation_idxs]
    return group_by_section(cited)


def group_by_section(
    citations: list[PlanningCitation],
) -> dict[str, list[PlanningCitation]]:
    by_section = {}
    for c in sorted(citations, key=lambda c: c.ordinance_id):
        by_section.setdefault(c.section or c.title, []).append(c)

    return by_section
