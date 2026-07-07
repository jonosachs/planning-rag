"""Deterministic geometry measurement at drawing scale.

Once features are identified (a boundary segment, a wall segment), the
distance between them is exact. A PDF point is 1/72 inch = 25.4/72 mm, so a
drawing at 1:N converts by that factor times N.
"""

import math

from spikes.geometry_extraction.schemas import Point, Segment

PT_TO_MM = 25.4 / 72  # 0.35277... mm per PDF point


def mm_per_point(scale_ratio: int) -> float:
    """Real-world mm represented by one PDF point at a 1:scale_ratio scale."""
    return PT_TO_MM * scale_ratio


def points_to_mm(distance_pt: float, scale_ratio: int) -> float:
    return distance_pt * mm_per_point(scale_ratio)


def point_to_segment(point: Point, segment: Segment) -> float:
    (x0, y0), (x1, y1) = segment.p0, segment.p1
    px, py = point
    dx, dy = x1 - x0, y1 - y0
    if dx == 0 and dy == 0:
        return math.dist(point, segment.p0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / (dx * dx + dy * dy)))
    return math.dist(point, (x0 + t * dx, y0 + t * dy))


def segment_to_segment(a: Segment, b: Segment) -> float:
    """Minimum distance between two segments (endpoint projections only).

    Ignores the crossing case, which is irrelevant for setback-style features
    that run alongside each other rather than intersecting.
    """
    return min(
        point_to_segment(a.p0, b),
        point_to_segment(a.p1, b),
        point_to_segment(b.p0, a),
        point_to_segment(b.p1, a),
    )


def min_distance(set_a: list[Segment], set_b: list[Segment]) -> float:
    """Nearest approach in points between any segment of A and any of B."""
    return min(segment_to_segment(a, b) for a in set_a for b in set_b)
