"""Extract reduced levels (RLs) from an elevation/section for height.

Building height = top RL (ridge or eaves) - natural ground RL. This extracts the
RL values (certified text) and types each by its nearest strong label. Typing is
a first pass only - "existing" tags many features, so the ridge/eaves/natural-
ground identification is refined by the model downstream (like setback ID).
"""

import math
import re

import fitz
from pydantic import BaseModel

RL_RE = re.compile(r"^\d{1,3}\.\d{2,3}$")  # e.g. 56.51, 50.53
LABEL_TYPES = {
    "ridge": ("ridge",),
    "eaves": ("eave", "eaves", "parapet"),
    "ffl": ("ffl", "fl."),
    "ground": ("natural", "ngl", "fgl", "ground"),  # natural/existing ground line
}
TYPE_RADIUS_PT = 35.0


class LevelReading(BaseModel):
    rl: float
    level_type: str | None  # ridge | eaves | ffl | ground | None (untyped)
    label: str | None
    x: float
    y: float


def extract_levels(page: fitz.Page) -> list[LevelReading]:
    words = page.get_text("words")
    tokens = [(w[4].strip(), ((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)) for w in words]
    labels = [(t.lower(), c) for t, c in tokens if t]

    levels = []
    for text, center in tokens:
        if not RL_RE.match(text):
            continue
        level_type, label = nearest_type(center, labels)
        levels.append(LevelReading(
            rl=float(text), level_type=level_type, label=label,
            x=center[0], y=center[1],
        ))
    return levels


def nearest_type(center, labels) -> tuple[str | None, str | None]:
    best = None
    for text, lc in labels:
        for level_type, keys in LABEL_TYPES.items():
            if any(k in text for k in keys):
                d = math.dist(lc, center)
                if d <= TYPE_RADIUS_PT and (best is None or d < best[0]):
                    best = (d, level_type, text)
    return (best[1], best[2]) if best else (None, None)


def overall_height_m(levels: list[LevelReading]) -> float | None:
    """max(ridge/eaves) - min(ground), if both present."""
    tops = [l.rl for l in levels if l.level_type in ("ridge", "eaves")]
    grounds = [l.rl for l in levels if l.level_type == "ground"]
    if not tops or not grounds:
        return None
    return round(max(tops) - min(grounds), 2)
