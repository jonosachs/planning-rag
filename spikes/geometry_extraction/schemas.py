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
