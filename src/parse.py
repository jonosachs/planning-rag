from bs4 import BeautifulSoup as bs
from ingest import ClauseDoc


def parse(html):
    soup = bs(html, "html.parser")
    return soup.get_text(separator="\n", strip=True)


def html_to_text(clause_docs) -> list[ClauseDoc]:
    for clause in clause_docs:
        html = clause.content
        text = parse(html)
        clause.content = text
    return clause_docs
