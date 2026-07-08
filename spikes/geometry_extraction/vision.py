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
    BoundaryOutline,
    BoundaryReport,
    BoundarySide,
    DimensionCandidate,
    DimensionSelection,
    ElementClassification,
    RegionChoice,
    SetbackAssessment,
    SetbackIdentification,
    SheetTitles,
    SiteRegions,
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
plan), whether any part of the PROPOSED DWELLING sits directly ON that boundary
(a zero setback) or is offset from it. Note the compass direction if a north
point is visible.

Use the CANDIDATE dimensions for values - do NOT read numbers off the image and
do NOT invent any. Attach every candidate that dimensions a distance to this
boundary and, for each, classify from the image:
- measures_to: what the far end reaches (proposed dwelling wall / existing
  boundary wall / fence / setout point / other)
- status: proposed, existing, retained, or unknown
- counts_as_setback: true ONLY when it measures boundary -> proposed dwelling
  wall. A dimension to an existing wall, fence, or setout point is NOT the
  dwelling setback.

Do not compute a governing value; code does that from counts_as_setback.
Explain the reasoning.

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


ELEMENT_PROMPT = """The dimension outlined in RED measures {value} mm. Look at
what its far end (away from the title boundary) reaches.

Set is_building_wall true ONLY if that far end lands directly on a wall of the
MAIN DWELLING/house that exists in the final scheme (proposed OR
retained-existing). Set it false if the end lands on any of: an existing boundary
wall or fence, a separate existing ancillary structure / outbuilding, a setout
point, or an INTERMEDIATE point of a running dimension chain (i.e. this dimension
is only one segment of a chain and does not by itself reach the dwelling).

Set is_proposed_dwelling true only for a proposed (new) dwelling wall.
measures_to: describe what the far end reaches. confidence: high/medium/low.
Do not report any other numbers."""


def classify_element(image_path: str, value_mm: int, temperature: float = 0.0) -> ElementClassification:
    client = genai.Client(api_key=_require_key())
    with open(image_path, "rb") as f:
        image = types.Part.from_bytes(data=f.read(), mime_type="image/png")
    response = client.models.generate_content(
        model=MODEL,
        contents=[image, ELEMENT_PROMPT.format(value=value_mm)],
        config={
            "response_mime_type": "application/json",
            "response_json_schema": ElementClassification.model_json_schema(),
            "temperature": temperature,
        },
    )
    return ElementClassification.model_validate_json(response.text)


REGIONS_PROMPT = """This is a proposed site plan. Return two shapes using
page-fraction coordinates where x is 0 at the left edge and 1 at the right edge,
y is 0 at the top edge and 1 at the bottom edge of THIS image.

1. building_polygon: trace the outline of the PROPOSED building / dwelling
   footprint (the main built mass) as closely as you can, as an ordered list of
   vertices. Include recesses/courtyards - follow the actual edge in and out.
2. boundary_top_line: two points for the site/title boundary line that runs
   along the TOP of the plan.

Do not report any dimension numbers. Only locate the shapes."""


BOUNDARY_PROMPT = """Trace the site / title boundary (the outer allotment
outline) on this site plan as an ordered list of polygon vertices, in
page-fraction coordinates where x is 0 at the left and 1 at the right, y is 0 at
the top and 1 at the bottom of the image. Follow the actual boundary line all the
way around. Do not report any dimension numbers."""


IDENTIFY_SETBACKS_PROMPT = """This is a proposed site plan. Identify the building
SETBACK dimensions - distances measured from a property/title boundary to a
building wall. For each setback give: role (front/rear/side), printed_label (the
dimension text exactly as printed, e.g. "nom 4400 (existing) to title"),
value_mm, measures_to (what the building end reaches, e.g. existing building
wall / proposed addition wall), status (existing/proposed/retained/unknown), and
x,y = the position of that dimension on the plan as page fractions (x: 0 left to
1 right, y: 0 top to 1 bottom).

List EACH distinct setback dimension separately, even if two have the same value
at different locations. Only boundary-to-building setbacks. Exclude internal room
dimensions, courtyard widths, and overall site/running dimensions."""


def identify_setbacks(image_path: str, temperature: float = 0.0) -> SetbackIdentification:
    client = genai.Client(api_key=_require_key())
    with open(image_path, "rb") as f:
        image = types.Part.from_bytes(data=f.read(), mime_type="image/png")
    response = client.models.generate_content(
        model=MODEL,
        contents=[image, IDENTIFY_SETBACKS_PROMPT],
        config={
            "response_mime_type": "application/json",
            "response_json_schema": SetbackIdentification.model_json_schema(),
            "temperature": temperature,
        },
    )
    return SetbackIdentification.model_validate_json(response.text)


ASSESS_BOUNDARIES_PROMPT = """This is a proposed site plan. For EACH side of the
site/title boundary (top, bottom, left, right of the plan), report:
- side (top/bottom/left/right) and role (front/rear/side)
- building_on_boundary: does the proposed building sit directly ON that boundary
  anywhere (a zero setback)?
- offsets: the setback/offset dimensions ALONG that side where the building steps
  away from the boundary. For each give value_mm, printed_label (exactly as
  printed), x,y (page-fraction position of the dimension), and status
  (existing/proposed/retained/unknown).

Do not invent numbers - read the printed dimensions. List each distinct offset
separately even if two share a value."""


def assess_boundaries(image_path: str, temperature: float = 0.0) -> BoundaryReport:
    client = genai.Client(api_key=_require_key())
    with open(image_path, "rb") as f:
        image = types.Part.from_bytes(data=f.read(), mime_type="image/png")
    response = client.models.generate_content(
        model=MODEL,
        contents=[image, ASSESS_BOUNDARIES_PROMPT],
        config={
            "response_mime_type": "application/json",
            "response_json_schema": BoundaryReport.model_json_schema(),
            "temperature": temperature,
        },
    )
    return BoundaryReport.model_validate_json(response.text)


STRIP_PROMPT = """This crop shows the {side} boundary of a site plan: the
property/title boundary runs along the {side} of the image, with the proposed
building adjacent to it.

Programmatically extracted candidate dimension values visible in this crop:
{candidates}

Report for THIS boundary only:
- side ({side}) and role (front/rear/side)
- building_on_boundary: does the proposed building sit directly ON this boundary
  anywhere (zero setback)?
- offsets: the setback dimensions from THIS boundary to the building, where it is
  set back. For each: value_mm, printed_label (exactly as printed), x,y
  (page-fraction position within THIS crop), status (existing/proposed/retained).

Read the printed dimensions - do not invent numbers. If a printed dimension is
only one segment of a running chain and does not by itself reach the building,
do not report it as a setback."""


def assess_boundary_strip(
    image_path: str,
    side: str,
    candidate_values: list[int] | None = None,
    temperature: float = 0.0,
) -> BoundarySide:
    client = genai.Client(api_key=_require_key())
    with open(image_path, "rb") as f:
        image = types.Part.from_bytes(data=f.read(), mime_type="image/png")
    candidates = ", ".join(str(v) for v in sorted(set(candidate_values or []))) or "none"
    response = client.models.generate_content(
        model=MODEL,
        contents=[image, STRIP_PROMPT.format(side=side, candidates=candidates)],
        config={
            "response_mime_type": "application/json",
            "response_json_schema": BoundarySide.model_json_schema(),
            "temperature": temperature,
        },
    )
    return BoundarySide.model_validate_json(response.text)


def extract_boundary_polygon(image_path: str, temperature: float = 0.0) -> BoundaryOutline:
    client = genai.Client(api_key=_require_key())
    with open(image_path, "rb") as f:
        image = types.Part.from_bytes(data=f.read(), mime_type="image/png")
    response = client.models.generate_content(
        model=MODEL,
        contents=[image, BOUNDARY_PROMPT],
        config={
            "response_mime_type": "application/json",
            "response_json_schema": BoundaryOutline.model_json_schema(),
            "temperature": temperature,
        },
    )
    return BoundaryOutline.model_validate_json(response.text)


def extract_site_regions(image_path: str, temperature: float = 0.0) -> SiteRegions:
    client = genai.Client(api_key=_require_key())
    with open(image_path, "rb") as f:
        image = types.Part.from_bytes(data=f.read(), mime_type="image/png")
    response = client.models.generate_content(
        model=MODEL,
        contents=[image, REGIONS_PROMPT],
        config={
            "response_mime_type": "application/json",
            "response_json_schema": SiteRegions.model_json_schema(),
            "temperature": temperature,
        },
    )
    return SiteRegions.model_validate_json(response.text)


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
