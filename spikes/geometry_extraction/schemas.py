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


class DimensionSelection(BaseModel):
    """The model's answer: which candidate, and why. It echoes the code value,
    it does not compute or read one."""

    answer_candidate_id: str | None
    value_mm: int | None
    classification: str  # e.g. "front_setback", "running_dimension", "internal"
    reason: str


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
