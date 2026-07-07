"""Build structured dimension candidates from page geometry.

Each candidate is pure geometry/fact: what the number is, what it measures out
to at scale, where it sits, how close each end is to the boundary, and what
text is nearby. No candidate is labelled a setback here - that's the model's
selection job downstream.
"""

import math

from spikes.geometry_extraction.measure import point_to_segment, points_to_mm
from spikes.geometry_extraction.schemas import (
    DimensionCandidate,
    PageGeometry,
    Point,
    Segment,
)

ON_LINE_TOL_PT = 3.0
LABEL_RADIUS_PT = 120.0


def build_dimension_candidates(
    geo: PageGeometry,
    scale_ratio: int,
    boundary: list[Segment],
) -> list[DimensionCandidate]:
    long_segs = [s for s in geo.segments if s.length > 15]
    labels = [
        t for t in geo.text_tokens
        if not t.text.strip().isdigit() and len(t.text.strip()) >= 3
    ]

    candidates: list[DimensionCandidate] = []
    seen: set[tuple[str, int]] = set()
    for tok in geo.text_tokens:
        text = tok.text.strip()
        if not (text.isdigit() and 300 <= int(text) <= 50000 and len(text) in (3, 4, 5)):
            continue
        near = min(long_segs, key=lambda s: point_to_segment(tok.center, s))
        if point_to_segment(tok.center, near) > ON_LINE_TOL_PT:
            continue
        key = (text, round(near.length))
        if key in seen:
            continue
        seen.add(key)

        horizontal = abs(near.p1[1] - near.p0[1]) < abs(near.p1[0] - near.p0[0])
        candidates.append(
            DimensionCandidate(
                id=f"d{len(candidates) + 1}",
                annotated_value=int(text),
                measured_mm=round(points_to_mm(near.length, scale_ratio)),
                orientation="horizontal" if horizontal else "vertical",
                x=round(tok.center[0] / geo.width, 3),
                y=round(tok.center[1] / geo.height, 3),
                end_a_to_boundary_pt=round(nearest(near.p0, boundary), 1),
                end_b_to_boundary_pt=round(nearest(near.p1, boundary), 1),
                nearby_labels=[
                    lbl.text for lbl in labels
                    if math.dist(lbl.center, tok.center) < LABEL_RADIUS_PT
                ][:6],
                line=(near.p0[0], near.p0[1], near.p1[0], near.p1[1]),
            )
        )
    return candidates


def nearest(point: Point, segments: list[Segment]) -> float:
    return min((point_to_segment(point, s) for s in segments), default=float("inf"))
