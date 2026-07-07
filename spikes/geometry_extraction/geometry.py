"""Extract generic vector primitives from a PDF drawing page.

Works on any vector PDF (e.g. a plotted .dwg): pulls line segments with their
style, text tokens with bounding boxes, and any "1:N" scale labels. No
per-office conventions are baked in here.
"""

import re

import fitz

from spikes.geometry_extraction.schemas import PageGeometry, Segment, TextToken

SCALE_RE = re.compile(r"1\s*:\s*(\d{1,4})")


def extract_page_geometry(page: fitz.Page) -> PageGeometry:
    return PageGeometry(
        page=page.number + 1,
        width=page.rect.width,
        height=page.rect.height,
        segments=extract_segments(page),
        text_tokens=extract_text_tokens(page),
        scale_labels=extract_scale_labels(page),
    )


def clip_geometry(geo: PageGeometry, rect: fitz.Rect) -> PageGeometry:
    """Restrict a page's geometry to one viewport rectangle."""
    return geo.model_copy(update={
        "segments": [
            s for s in geo.segments
            if rect.contains(fitz.Point((s.p0[0] + s.p1[0]) / 2, (s.p0[1] + s.p1[1]) / 2))
        ],
        "text_tokens": [t for t in geo.text_tokens if rect.contains(fitz.Point(t.center))],
    })


def extract_segments(page: fitz.Page) -> list[Segment]:
    segments = []
    for drawing in page.get_drawings():
        style = {
            "width": drawing.get("width"),
            "color": drawing.get("color"),
            "dashes": drawing.get("dashes"),
        }
        for item in drawing["items"]:
            if item[0] != "l":  # only straight line segments for now
                continue
            p0, p1 = item[1], item[2]
            segments.append(
                Segment(p0=(p0.x, p0.y), p1=(p1.x, p1.y), **style)
            )
    return segments


def extract_text_tokens(page: fitz.Page) -> list[TextToken]:
    tokens = []
    for word in page.get_text("words"):
        x0, y0, x1, y1, text = word[:5]
        text = text.strip()
        if text:
            tokens.append(TextToken(text=text, bbox=(x0, y0, x1, y1)))
    return tokens


def extract_scale_labels(page: fitz.Page) -> list[str]:
    labels = []
    for match in SCALE_RE.finditer(page.get_text()):
        label = f"1:{match.group(1)}"
        if label not in labels:
            labels.append(label)
    return labels
