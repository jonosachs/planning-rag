from chunk import chunk_clause
from tests.sample_clauses import sample_clauses
from ingest import get_scheme_clauses
from parse import html_to_text

# clauses_html = get_scheme_clauses("Melbourne", 10)
clauses_html = sample_clauses
clauses_text = html_to_text(clauses_html)
clause_chunks = chunk_clause(clauses_text[6])
print(clause_chunks)
