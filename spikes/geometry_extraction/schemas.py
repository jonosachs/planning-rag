"""Generic vector primitives extracted from a drawing sheet.

Deliberately convention-free: a Segment carries raw geometry and whatever
style attributes the PDF happens to expose, but nothing here decides what a
segment *means* (boundary, wall, dimension line...). That interpretation is
the model's job in a later slice; this layer only reports what is on the page.
"""

import math

from pydantic import BaseModel

Point = tuple[float, float]


class Segment(BaseModel):
    p0: Point
    p1: Point
    width: float | None = None
    color: tuple[float, float, float] | None = None
    dashes: str | None = None

    @property
    def length(self) -> float:
        return math.dist(self.p0, self.p1)

    @property
    def is_dashed(self) -> bool:
        # PyMuPDF reports a solid line as "[] 0"; anything else is patterned.
        return bool(self.dashes) and self.dashes.strip() not in ("[] 0", "")


class TextToken(BaseModel):
    text: str
    bbox: tuple[float, float, float, float]

    @property
    def center(self) -> Point:
        x0, y0, x1, y1 = self.bbox
        return ((x0 + x1) / 2, (y0 + y1) / 2)


class PageGeometry(BaseModel):
    page: int
    width: float
    height: float
    segments: list[Segment]
    text_tokens: list[TextToken]
    scale_labels: list[str]  # e.g. ["1:100", "1:50"] as found in sheet text


class DimensionCandidate(BaseModel):
    """A dimension reduced to geometry facts - no interpretation of meaning.

    Values here are code-measured/extracted, never read by the model. The model
    consumes these to *select* which candidate answers a question.
    """

    id: str
    annotated_value: int  # the number printed on the sheet (code-extracted)
    measured_mm: int  # geometric span * scale (code-measured)
    orientation: str  # "horizontal" | "vertical"
    x: float  # page-fraction position of the label
    y: float
    end_a_to_boundary_pt: float  # nearest title-boundary distance, each end
    end_b_to_boundary_pt: float
    nearby_labels: list[str]  # non-numeric text tokens near the dimension
    line: tuple[float, float, float, float] | None = None  # dim-line seg in page pt


class Vertex(BaseModel):
    x: float  # page fraction 0-1 within the crop (left to right)
    y: float  # page fraction 0-1 within the crop (top to bottom)


class SiteRegions(BaseModel):
    """Rough regions the model locates - no values, no conventions.

    Vision only outlines *where* things are; code measures the gaps.
    """

    building_polygon: list[Vertex]  # proposed dwelling footprint
    boundary_top_line: list[Vertex]  # the boundary edge along the top of the crop


class FeatureVerification(BaseModel):
    """Result of one focused verification: general, query-agnostic.

    The QUESTION is supplied per task (query-derived); this shape is reused for
    any 'look at this one marked feature and judge it' check.
    """

    finding: str  # the model's answer to the focused question
    holds: bool  # true if the asserted condition holds
    confidence: str  # "high" | "medium" | "low"
    reasoning: str


class ElementClassification(BaseModel):
    measures_to: str  # proposed dwelling wall / existing wall / fence / setout / other
    is_proposed_dwelling: bool
    confidence: str  # "high" | "medium" | "low"
    reasoning: str


class DimensionSelection(BaseModel):
    """The model's answer: which candidate, and why. It echoes the code value,
    it does not compute or read one."""

    answer_candidate_id: str | None
    value_mm: int | None
    classification: str  # e.g. "front_setback", "running_dimension", "internal"
    reason: str


class AttachedDimension(BaseModel):
    candidate_id: str
    value_mm: int  # echoed from the candidate, never invented
    measures_to: str  # e.g. "proposed dwelling wall", "existing boundary wall", "fence", "setout point"
    status: str  # "proposed" | "existing" | "retained" | "unknown"
    counts_as_setback: bool  # true only when boundary -> proposed dwelling wall


class BoundarySetback(BaseModel):
    side: str  # "top" | "bottom" | "left" | "right" (page-relative)
    compass: str | None  # e.g. "north", if a north point is visible
    building_on_boundary: bool  # any part of the proposed dwelling sits on this boundary
    dimensions: list[AttachedDimension]
    reasoning: str


class SetbackAssessment(BaseModel):
    boundaries: list[BoundarySetback]


class SheetTitles(BaseModel):
    """Sub-drawing titles the model reads off the sheet (verbatim as printed)."""

    titles: list[str]


class LabelledViewport(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float
    title: str | None  # the sub-drawing title sitting directly beneath it


class RegionChoice(BaseModel):
    """Where the model says to zoom in for a given question.

    bbox is in page fractions (0-1) so it's independent of render resolution;
    the model only localises, it never reads values.
    """

    x0: float
    y0: float
    x1: float
    y1: float
    reason: str
    expected_features: list[str]
