"""General focused-verification primitive - query-agnostic.

Isolate one feature, outline it in red on a tight crop, ask one focused question
at temperature 0, return a structured verdict with confidence. Nothing here
knows about setbacks: the QUESTION is supplied per task (derived from the user
query + planning control), and the same mechanism serves any "look at this one
marked feature and judge it" check. Reliability comes from isolation + marking +
determinism; callers add geometric cross-checks and fail-closed handling.
"""

import os

import fitz
from dotenv import load_dotenv
from google import genai
from google.genai import types

from spikes.geometry_extraction.schemas import FeatureVerification

load_dotenv()

MODEL = "gemini-3-flash-preview"

VERIFY_PROMPT = """The feature outlined in RED is the subject. Look only at it and
its immediate context on this drawing crop.

{question}

Return: finding (your answer), holds (true only if the asserted condition is
true), confidence (high/medium/low), and what you see. Do not report unrelated
numbers or features."""


def verify_feature(
    pdf_path: str,
    page_number: int,
    mark_box: tuple[float, float, float, float],
    question: str,
    out_path: str = "tmp/verify_crop.png",
    margin: float = 240.0,
    zoom: float = 6.0,
    temperature: float = 0.0,
) -> FeatureVerification:
    render_marked_crop(pdf_path, page_number, mark_box, out_path, margin, zoom)
    client = genai.Client(api_key=_require_key())
    with open(out_path, "rb") as f:
        image = types.Part.from_bytes(data=f.read(), mime_type="image/png")
    response = client.models.generate_content(
        model=MODEL,
        contents=[image, VERIFY_PROMPT.format(question=question)],
        config={
            "response_mime_type": "application/json",
            "response_json_schema": FeatureVerification.model_json_schema(),
            "temperature": temperature,
        },
    )
    return FeatureVerification.model_validate_json(response.text)


def render_marked_crop(
    pdf_path: str,
    page_number: int,
    mark_box: tuple[float, float, float, float],
    out_path: str,
    margin: float,
    zoom: float,
) -> str:
    page = fitz.open(pdf_path)[page_number]
    box = fitz.Rect(*mark_box)
    page.draw_rect(box, color=(1, 0, 0), width=2)
    crop = fitz.Rect(box.x0 - margin, box.y0 - margin,
                     box.x1 + margin, box.y1 + margin) & page.rect
    page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=crop, alpha=False).save(out_path)
    return out_path


def _require_key() -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not found")
    return key
