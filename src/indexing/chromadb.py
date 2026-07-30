from src.indexing.interfaces import VectorStore
from src.indexing.schemas import EmbeddedChunk
from chromadb.api import ClientAPI
from chromadb.api.types import GetResult, Metadata, QueryResult
from pydantic import BaseModel
from typing import cast
import chromadb
import uuid


class ChromaDb(VectorStore):
    def __init__(self, collection_name: str, client: ClientAPI | None = None):
        self.client = client or chromadb.PersistentClient(path="./chroma_db")
        self.collection = collection_name

    def delete_collection(self):
        try:
            self.client.delete_collection(self.collection)
        except Exception as e:
            raise RuntimeError(f"⚠️ Failed to delete db {self.collection}: {e}") from e

    def write(self, embedded_chunks: list[EmbeddedChunk]) -> None:
        collection = self.client.get_or_create_collection(name=self.collection)
        for chunk in embedded_chunks:
            scheme_id = chunk.metadata.scheme_id
            ordinance_id = chunk.metadata.ordinance_id
            chunk_index = chunk.metadata.chunk_index

            try:
                metadata = (
                    chunk.metadata.model_dump()
                    if isinstance(chunk.metadata, BaseModel)
                    else chunk.metadata
                )
                collection.upsert(
                    ids=[f"{scheme_id}:{ordinance_id}:{chunk_index}"],
                    documents=[chunk.text],
                    embeddings=[chunk.embedded_text],
                    metadatas=[cast(Metadata, metadata)],
                )
            except ValueError as e:
                raise RuntimeError(f"⚠️ Failed to write to db: {e}") from e

    # Query by vector similarity
    def run_query(
        self, embedded_query: list[float], n_results: int = 10
    ) -> QueryResult:
        collection = self.client.get_or_create_collection(name=self.collection)
        results = collection.query(
            query_embeddings=[embedded_query], n_results=n_results
        )
        return results

    def get_all(self) -> GetResult:
        collection = self.client.get_or_create_collection(name=self.collection)
        records = collection.get(include=["documents", "metadatas"])
        return records
