from src.chunk import MetaData
from src.embed import EmbeddedChunk
from dataclasses import asdict
import chromadb

client = chromadb.PersistentClient(path="./chroma_db")


def delete_db_collection(name):
    client.delete_collection(name)


# Add documents with embeddings
def write_to_db(name: str, embedded_chunks: list[EmbeddedChunk]):
    collection = client.get_or_create_collection(name=name)
    for chunk in embedded_chunks:
        md = chunk.metadata
        if type(md) is dict:
            md = MetaData(**md)
        doc_id = f"{md.scheme_id}:{md.semantic_number}:{md.chunk_index}"
        try:
            collection.upsert(
                ids=[doc_id],
                documents=[chunk.text],
                embeddings=[chunk.embedded_text],
                metadatas=[asdict(md)],
            )
        except ValueError as e:
            raise RuntimeError(f"Failed to write to db: {e}") from e


# Query by vector similarity
def query_db(name: str, embedded_query: list[float], n_results: int = 10):
    collection = client.get_or_create_collection(name=name)
    results = collection.query(query_embeddings=[embedded_query], n_results=n_results)
    return results


def get_records_from_db(name: str) -> dict:
    collection = client.get_or_create_collection(name=name)
    records = collection.get(include=["documents", "metadatas"])
    return records["ids"]
