from dataclasses import dataclass
from google import genai
from src.chunk import Chunk, MetaData
from google.genai import errors
from dotenv import load_dotenv
import os

load_dotenv()


@dataclass
class EmbeddedChunk:
    text: str
    metadata: MetaData
    embedded_text: list[float]


def embed_text(text: str) -> list:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    try:
        result = client.models.embed_content(
            model="gemini-embedding-001", contents=text
        )

    except errors.APIError as e:
        raise RuntimeError(f"Embedding error: {e.code} {e.message}") from e

    return result.embeddings[0].values


def batch_embed(chunks: list[Chunk]) -> list[EmbeddedChunk]:
    embedded_chunks = []
    for c in chunks:
        prefix = (
            f"Planning scheme: {c.metadata.scheme_id}\n"
            f"Clause: {c.metadata.semantic_number} {c.metadata.title}\n"
        )
        embedded_text = embed_text(prefix + c.text)
        embedded_chunks.append(
            EmbeddedChunk(text=c.text, metadata=c.metadata, embedded_text=embedded_text)
        )

    return embedded_chunks
