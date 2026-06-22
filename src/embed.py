from dataclasses import dataclass
from google import genai
from src.chunk import Chunk, MetaData
from google.genai import errors
from dotenv import load_dotenv
import os
import time

load_dotenv()


@dataclass
class EmbeddedChunk:
    text: str
    metadata: MetaData
    embedded_text: list[float]


def embed_text(text: str) -> list:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    max_attempts = 3
    sleep_seconds = 60

    for num_attempts in range(max_attempts):
        try:
            result = client.models.embed_content(
                model="gemini-embedding-001", contents=text
            )

            return result.embeddings[0].values

        except errors.APIError as e:
            print(f"❌ Embedding error: {e.code} {e.message}")

        if num_attempts < max_attempts - 1:
            print(f"⛑️ Retrying in {sleep_seconds} seconds..")
            time.sleep(sleep_seconds)

    raise RuntimeError("⚠️ Failed to embed")


def batch_embed(chunks: list[Chunk]) -> list[EmbeddedChunk]:
    embedded_chunks = []
    for c in chunks:
        prefix = (
            f"Planning scheme: {c.metadata.scheme_id}\n"
            f"Clause: {c.metadata.ordinance_id} {c.metadata.title}\n"
        )
        embedded_text = embed_text(prefix + c.text)
        embedded_chunks.append(
            EmbeddedChunk(text=c.text, metadata=c.metadata, embedded_text=embedded_text)
        )
        print(f"ℹ️ Embedded {len(embedded_chunks)} chunks")

    return embedded_chunks
