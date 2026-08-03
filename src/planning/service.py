from src.indexing.interfaces import DataSource
from src.planning.chunk import batch_chunk
from src.planning.pipeline import run_fetch_scheme_pipeline


class PlanningSource(DataSource):
    def __init__(
        self, planning_scheme: str, key_word: str | None = None, max_results: int = 100
    ):
        self._planning_scheme = planning_scheme
        self._key_word = key_word
        self.max_results = max_results

    def load(self):
        clauses = run_fetch_scheme_pipeline(
            scheme=self._planning_scheme,
            key_word=self._key_word,
            max_results=self.max_results,
        )
        return clauses

    def chunk(self, items):
        chunks = batch_chunk(items)
        return chunks
