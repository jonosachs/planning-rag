"""Segment a multi-drawing sheet into its viewports via PDF clip rects.

CAD sheets place several drawings on one page, each rendered inside a clip
(scissor) rectangle - often at different scales. Recovering those rects lets us
work one drawing at a time: a single scale and a single boundary, not the
whole-sheet soup. Nothing here is convention-specific; it reads the PDF's own
clip geometry.
"""

from collections import defaultdict

import fitz

MIN_PATHS = 10  # ignore clip rects with too few paths to be a real drawing
MIN_AREA_FRAC = 0.02
MAX_AREA_FRAC = 0.97  # drop the full-page frame
MERGE_TOL_PT = 8.0


def extract_viewports(page: fitz.Page) -> list[fitz.Rect]:
    counts = count_paths_by_scissor(page)
    kept = filter_rects(counts, page.rect)
    return merge_similar(kept)


def count_paths_by_scissor(page: fitz.Page) -> dict[tuple[int, int, int, int], int]:
    counts: dict[tuple[int, int, int, int], int] = defaultdict(int)
    for path in page.get_drawings(extended=True):
        scissor = path.get("scissor")
        if scissor is None:
            continue
        key = (round(scissor.x0), round(scissor.y0), round(scissor.x1), round(scissor.y1))
        counts[key] += 1
    return counts


def filter_rects(
    counts: dict[tuple[int, int, int, int], int],
    page_rect: fitz.Rect,
) -> list[tuple[fitz.Rect, int]]:
    page_area = page_rect.width * page_rect.height
    kept = []
    for (x0, y0, x1, y1), n in counts.items():
        rect = fitz.Rect(x0, y0, x1, y1) & page_rect  # clamp off-page geometry
        if n < MIN_PATHS or rect.is_empty:
            continue
        frac = (rect.width * rect.height) / page_area
        if not (MIN_AREA_FRAC < frac < MAX_AREA_FRAC):
            continue
        kept.append((rect, n))
    return kept


def merge_similar(rects: list[tuple[fitz.Rect, int]]) -> list[fitz.Rect]:
    """Collapse near-duplicate clip rects, keeping the higher path count."""
    ordered = sorted(rects, key=lambda rn: rn[1], reverse=True)
    merged: list[fitz.Rect] = []
    for rect, _ in ordered:
        if any(_similar(rect, kept) for kept in merged):
            continue
        merged.append(rect)
    return merged


def _similar(a: fitz.Rect, b: fitz.Rect) -> bool:
    return (
        abs(a.x0 - b.x0) < MERGE_TOL_PT
        and abs(a.y0 - b.y0) < MERGE_TOL_PT
        and abs(a.x1 - b.x1) < MERGE_TOL_PT
        and abs(a.y1 - b.y1) < MERGE_TOL_PT
    )
