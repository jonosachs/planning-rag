from src.indexing.interfaces import VectorStore
from src.indexing.schemas import EmbeddedChunk
import chromadb
import uuid


class ChromaDb(VectorStore):
    def __init__(self, collection_name: str, client=None):
        self.client = client or chromadb.PersistentClient(path="./chroma_db")
        self.collection = collection_name

    def delete_collection(self):
        try:
            self.client.delete_collection(self.collection)
        except Exception as e:
            raise RuntimeError(f"⚠️ Failed to delete db {self.collection}: {e}") from e

    def write(self, embedded_chunks: list[EmbeddedChunk], collection_name):
        collection = self.client.get_or_create_collection(name=collection_name)
        for chunk in embedded_chunks:
            try:
                collection.upsert(
                    ids=[uuid.uuid4()],
                    documents=[chunk.text],
                    embeddings=[chunk.embedded_text],
                    metadatas=[chunk.metadata],
                )
            except ValueError as e:
                raise RuntimeError(f"⚠️ Failed to write to db: {e}") from e

    # Query by vector similarity
    def run_query(self, embedded_query: list[float], n_results: int = 10) -> dict:
        collection = self.client.get_or_create_collection(name=self.collection)
        results = collection.query(
            query_embeddings=[embedded_query], n_results=n_results
        )
        return results

    def get_all(self, collection_name) -> dict:
        collection = self.client.get_or_create_collection(name=collection_name)
        records = collection.get(include=["documents", "metadatas"])
        return records
