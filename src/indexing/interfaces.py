from abc import ABC, abstractmethod
from src.indexing.schemas import Chunk, EmbeddedChunk


class DataSource(ABC):
    @abstractmethod
    def load(self) -> list:
        raise NotImplementedError

    @abstractmethod
    def chunk(self, items: list) -> list[Chunk]:
        raise NotImplementedError


class Embedder(ABC):
    @abstractmethod
    def embed_chunks(self, chunks: list[Chunk]) -> list[EmbeddedChunk]:
        raise NotImplementedError

    def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError


class VectorStore(ABC):
    @abstractmethod
    def write(self, embedded_chunks: list[EmbeddedChunk]):
        raise NotImplementedError

    @abstractmethod
    def run_query(self, embedded_query: list[float], n_results: int = 10) -> dict:
        raise NotImplementedError

    @abstractmethod
    def get_all(self) -> dict:
        raise NotImplementedError
