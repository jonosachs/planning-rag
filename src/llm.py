import os
from dotenv import load_dotenv
from google import genai
from google.genai import errors
from src.prompt import system_prompt
import time
from pydantic import BaseModel, Field
from typing import Optional

load_dotenv()

API_KEY = os.environ["GEMINI_API_KEY"]
CLIENT = genai.Client(api_key=API_KEY)


class Citation(BaseModel):
    scheme_id: str
    ordinance_id: str
    chunk_index: str
    title: str


class Response(BaseModel):
    answer: str = Field(
        description="Answer if it can be deduced from the context. Otherwise say you don't know."
    )
    citations: Optional[list[Citation]] = Field(
        description="""
        Citations for all context used in your answer. 
        Only 'None' if the answer is not in the context
        """,
        default=None,
    )


def fetch_llm_response(user_query, context, max_attempts=3, client=None):
    # use default google model if no argument provided
    client = client or CLIENT

    prompt = f"{system_prompt}\nUser query:{user_query}\nContext: {context}"

    print("📡 Fetching response from LLM API..")
    for attempt in range(max_attempts):
        try:
            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_json_schema": Response.model_json_schema(),
                },
            )

            summaries = Response.model_validate_json(response.text)
            return summaries

        except errors.APIError as e:
            print(f"⚠️ API error {e} retrying..")
        except Exception as e:
            print(f"⚠️ Unexpected error {e}, retrying.. ")

        if attempt < max_attempts - 1:
            time.sleep(3**attempt)  # exponential backoff

    raise RuntimeError("⚠️ Could not resolve error, aborting")
