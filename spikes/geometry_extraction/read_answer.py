"""Generic read-and-compare: read stated values off the selected page(s), assess.

Ties the pieces together for any query with no per-metric extractor:
  1. fuzzy-select the relevant page(s) from the feature manifest,
  2. retrieve the relevant planning controls (RAG),
  3. the model reads the value(s) relevant to the query off the page image(s),
  4. code guards each value against the page text (no invented numbers),
  5. the model compares to the controls and cites them.
"""

import os
import re

import fitz
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel

from src.query.schemas import PlanningCitation
from spikes.geometry_extraction.compliance import retrieve_controls
from spikes.geometry_extraction.manifest import build_page_manifest, format_manifest
from spikes.geometry_extraction.schemas import PageSelection
from spikes.geometry_extraction.vision import select_pages

load_dotenv()
MODEL = "gemini-3-flash-preview"
MAX_PAGE_CHARS = 15000

READ_PROMPT = """You are answering a planning question by reading values directly
off the selected drawing page(s) and comparing them to the planning controls.

Question: {query}

Planning controls (retrieved from the scheme):
{controls}

Drawing page text (use ONLY values that appear here - do not invent numbers):
{page_text}

The same page(s) are attached as images. Read the value(s) relevant to the
question (e.g. from a site-statistics or data block) and put each stated value you
rely on in values_read, verbatim as printed. Assess compliance against the
controls: complies true / false / null if it cannot be determined. Explain and
cite the controls."""


class DrawingAnswer(BaseModel):
    values_read: list[str]
    complies: bool | None
    reasoning: str
    citations: list[PlanningCitation]


def assess_query(query: str, drawing_set: list[str]) -> tuple[PageSelection, DrawingAnswer, list[str]]:
    manifest = build_page_manifest(drawing_set)
    selection = select_pages(query, format_manifest(manifest))
    controls = retrieve_controls(query)
    page_text, images = gather_pages(selection)
    answer = read_and_compare(query, controls, page_text, images)
    # guard: every number the model read must appear in the page text (the model
    # may paraphrase "label: value", so check the digits, not the whole string)
    invented = [v for v in answer.values_read
                if not all(n in page_text for n in re.findall(r"\d+(?:\.\d+)?", v))]
    return selection, answer, invented


def gather_pages(selection: PageSelection) -> tuple[str, list[str]]:
    texts, images = [], []
    for i, ref in enumerate(selection.selections):
        page = fitz.open(ref.pdf)[ref.page - 1]
        texts.append(f"[{ref.pdf} p.{ref.page}]\n{page.get_text()}")
        path = f"tmp/read_{i}.png"
        page.get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False).save(path)
        images.append(path)
    return "\n\n".join(texts)[:MAX_PAGE_CHARS], images


def read_and_compare(query, controls, page_text, image_paths) -> DrawingAnswer:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    parts = []
    for path in image_paths:
        with open(path, "rb") as f:
            parts.append(types.Part.from_bytes(data=f.read(), mime_type="image/png"))
    parts.append(READ_PROMPT.format(query=query, controls=controls, page_text=page_text))
    response = client.models.generate_content(
        model=MODEL,
        contents=parts,
        config={
            "response_mime_type": "application/json",
            "response_json_schema": DrawingAnswer.model_json_schema(),
            "temperature": 0.0,
        },
    )
    return DrawingAnswer.model_validate_json(response.text)
