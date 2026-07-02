from src.indexing.interfaces import Embedder
from src.indexing.schemas import Chunk, EmbeddedChunk
from google import genai
from google.genai import errors
from google.genai.client import Client
from dotenv import load_dotenv
import time
import os

load_dotenv()


class GeminiEmbedder(Embedder):
    def __init__(self, client: Client | None = None, model: str | None = None):
        if client and model:
            self._client = client
            self._model = model
        else:
            self._build_default_client()

        self._max_attempts = 3
        self._sleep_seconds = 60

    def _build_default_client(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("API key not found")

        self._client = genai.Client(api_key=api_key)
        self._model = "gemini-embedding-001"

    def _fetch_embedding(self, text: str) -> list:
        for num_attempts in range(self._max_attempts):
            try:
                result = self._client.models.embed_content(
                    model=self._model, contents=text
                )

                return result.embeddings[0].values

            except errors.APIError as e:
                print(f"❌ Embedding error: {e.code} {e.message}")

            if num_attempts < self._max_attempts - 1:
                print(f"⛑️ Retrying in {self._sleep_seconds} seconds..")
                time.sleep(self._sleep_seconds)

        raise RuntimeError("⚠️ Failed to embed")

    def embed_text(self, text: str) -> list[float]:
        return self._fetch_embedding(text)

    def embed_chunks(self, chunks: list[Chunk]) -> list[EmbeddedChunk]:
        embedded_chunks = []
        for c in chunks:
            embedded_text = self._fetch_embedding(c.text)
            embedded_chunks.append(
                EmbeddedChunk(
                    text=c.text, metadata=c.metadata, embedded_text=embedded_text
                )
            )
            print(f"ℹ️ Embedded {len(embedded_chunks)} chunks")

        return embedded_chunks
