from google import genai
from dotenv import load_dotenv
import os

load_dotenv()


def embed(contents: str) -> list:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    result = client.models.embed_content(
        model="gemini-embedding-001", contents=contents
    )
    return result
