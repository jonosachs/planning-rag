from src.indexing.interfaces import DataSource
from src.planning.chunk import batch_chunk


class PlanningSource(DataSource):
    def __init__(self, planning_scheme: str, key_word: str | None = None):
        self._planning_scheme = planning_scheme
        self._key_word = key_word
        pass

    def load(self):
        clauses = run_fetch_scheme_pipeline(
            scheme=self._planning_scheme,
            key_word=self._key_word,
            max_results=100,
        )
        return clauses

    def chunk(self, items):
        chunks = batch_chunk(items)
        return chunks
