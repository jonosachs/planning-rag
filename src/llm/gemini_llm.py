import os
from dotenv import load_dotenv
from google import genai
from google.genai import errors
import time
from google.genai.client import Client
from pydantic import BaseModel

load_dotenv()


class GeminiLlm:
    def __init__(
        self,
        schema: type[BaseModel],
        client: Client | None = None,
        model: str | None = None,
    ):
        if client and model:
            self._client = client
            self._model = model
        else:
            self._build_default_client()

        self._schema = schema
        self._max_retries = 3

    def _build_default_client(self) -> object:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("API key not found")

        self._client = genai.Client(api_key=api_key)
        self._model = "gemini-3-flash-preview"

    def get_response(self, prompt):
        for attempt in range(self._max_retries):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_json_schema": self._schema.model_json_schema(),
                    },
                )

                validated = self._schema.model_validate_json(response.text)
                return validated

            except errors.APIError as e:
                if attempt < self._max_retries - 1:
                    print(f"⚠️ API error {e} retrying..")
                    time.sleep(3**attempt)  # exponential backoff
            except Exception as e:
                raise RuntimeError("⚠️ Unexpected error") from e

        raise RuntimeError("⚠️ Could not resolve API error")
