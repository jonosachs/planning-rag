"""Model-driven region picking (localisation only, no value reading).

The model sees a rendered sheet and the question, and returns a page-fraction
bbox to zoom into. Deterministic geometry extraction then runs on that clip.
Kept inside the spike so the app's LLM wrapper stays untouched.
"""

import os

import fitz
from dotenv import load_dotenv
from google import genai
from google.genai import types

from spikes.geometry_extraction.schemas import (
    DimensionCandidate,
    DimensionSelection,
    RegionChoice,
    SetbackAssessment,
    SheetTitles,
)

load_dotenv()

MODEL = "gemini-3-flash-preview"

TITLES_PROMPT = """List the title of every separate sub-drawing on this sheet,
exactly as printed (e.g. 'PROPOSED SITE PLAN'). Titles only - not scales, notes,
or the title block. Do not read dimensions."""

SELECT_PROMPT = """You are selecting which dimension answers a planning question
from a list of candidates already extracted and measured from the drawing.

Do NOT compute or invent a value. If you choose a candidate, echo its
measured_mm exactly into value_mm.

Each candidate gives: annotated_value (printed number), measured_mm (measured at
scale by code), orientation, x/y page position, how close each end is to the
title boundary (points), and nearby text labels. A setback runs boundary->wall,
so one end is near the boundary and the other is not, and nearby labels name the
boundary and a building element. Running/site dimensions have both ends near the
boundary. Internal dimensions have neither end near the boundary.

Pick the single best candidate, classify it, and explain why. If none fits,
return null ids.

Question: {question}

Candidates:
{candidates}
"""

REGION_PROMPT = """You are locating where to inspect an architectural drawing
sheet to answer a planning question. Do NOT answer the question and do NOT read
any dimension values.

Return a single rectangular region to zoom into, as fractions of the page
(x0,y0 = top-left, x1,y1 = bottom-right, each 0-1). Make the region large
enough to contain the whole relationship being asked about - e.g. for a setback
it must include both the site boundary and the relevant building wall, not just
a label. Also list the features you expect to find there.

Question: {question}
"""


SETBACK_PROMPT = """You are assessing setbacks on a proposed site plan.

Use the IMAGE to judge, for each boundary edge (top, bottom, left, right of the
plan), whether any part of the building sits directly ON that boundary (a zero
setback) or is offset from it. Note the compass direction if a north point is
visible.

Use the CANDIDATE dimensions for values - do NOT read numbers off the image and
do NOT invent any. When a boundary has a dimensioned setback, attach the
matching candidate(s) and echo their annotated_value into dimensioned_setbacks_mm.

For each boundary set governing_setback_mm = 0 if the building is on it,
otherwise the minimum of its dimensioned setbacks. Explain the reasoning.

Candidates:
{candidates}
"""


def assess_setbacks(
    image_path: str,
    candidates: list[DimensionCandidate],
) -> SetbackAssessment:
    client = genai.Client(api_key=_require_key())
    with open(image_path, "rb") as f:
        image = types.Part.from_bytes(data=f.read(), mime_type="image/png")
    candidate_json = "\n".join(c.model_dump_json() for c in candidates)
    response = client.models.generate_content(
        model=MODEL,
        contents=[image, SETBACK_PROMPT.format(candidates=candidate_json)],
        config={
            "response_mime_type": "application/json",
            "response_json_schema": SetbackAssessment.model_json_schema(),
        },
    )
    return SetbackAssessment.model_validate_json(response.text)


def list_titles(image_path: str) -> list[str]:
    client = genai.Client(api_key=_require_key())
    with open(image_path, "rb") as f:
        image = types.Part.from_bytes(data=f.read(), mime_type="image/png")
    response = client.models.generate_content(
        model=MODEL,
        contents=[image, TITLES_PROMPT],
        config={
            "response_mime_type": "application/json",
            "response_json_schema": SheetTitles.model_json_schema(),
        },
    )
    return SheetTitles.model_validate_json(response.text).titles


def render_sheet(page: fitz.Page, out_path: str, max_width: int = 2000) -> str:
    zoom = max_width / page.rect.width
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    pix.save(out_path)
    return out_path


def pick_region(question: str, image_path: str) -> RegionChoice:
    client = genai.Client(api_key=_require_key())
    with open(image_path, "rb") as f:
        image = types.Part.from_bytes(data=f.read(), mime_type="image/png")

    response = client.models.generate_content(
        model=MODEL,
        contents=[image, REGION_PROMPT.format(question=question)],
        config={
            "response_mime_type": "application/json",
            "response_json_schema": RegionChoice.model_json_schema(),
        },
    )
    return RegionChoice.model_validate_json(response.text)


def select_dimension(
    question: str,
    candidates: list[DimensionCandidate],
) -> DimensionSelection:
    client = genai.Client(api_key=_require_key())
    candidate_json = "\n".join(c.model_dump_json() for c in candidates)
    response = client.models.generate_content(
        model=MODEL,
        contents=[SELECT_PROMPT.format(question=question, candidates=candidate_json)],
        config={
            "response_mime_type": "application/json",
            "response_json_schema": DimensionSelection.model_json_schema(),
        },
    )
    return DimensionSelection.model_validate_json(response.text)


def region_to_rect(region: RegionChoice, page: fitz.Page) -> fitz.Rect:
    w, h = page.rect.width, page.rect.height
    return fitz.Rect(region.x0 * w, region.y0 * h, region.x1 * w, region.y1 * h)


def _require_key() -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not found")
    return key
