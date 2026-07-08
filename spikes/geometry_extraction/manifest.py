"""Page-by-page feature manifest for fuzzy page selection.

For each page across the drawing set, pull a compact list of salient text -
titles, headings, labels, block names, notable annotations (e.g. "SITE
STATISTICS", "total site area", "PROPOSED SITE PLAN", "RIDGE RL"). The model
fuzzy-matches a query against this manifest to choose the best page(s), instead
of any hard-coded, per-label extractor - so it generalises to plans that label
things differently.
"""

import re
from dataclasses import dataclass

import fitz

LEVEL_RE = re.compile(r"\d+\.\d{2,3}")  # spot levels / RLs / codes-with-levels
MAX_FEATURES = 150  # comprehensive enough that query-relevant blocks aren't cut


@dataclass
class PageFeatures:
    pdf: str
    page: int
    features: list[str]


def build_page_manifest(pdf_paths: list[str], max_features: int = MAX_FEATURES) -> list[PageFeatures]:
    manifest = []
    for path in pdf_paths:
        for page in fitz.open(path):
            manifest.append(PageFeatures(path, page.number + 1, salient_lines(page, max_features)))
    return manifest


def salient_lines(page: fitz.Page, cap: int) -> list[str]:
    """Salient text lines, ranked by font size (headings/block titles first)."""
    by_text: dict[str, tuple[str, float]] = {}
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            text = " ".join(" ".join(s["text"] for s in line["spans"]).split())
            size = max((s["size"] for s in line["spans"]), default=0.0)
            if not (3 <= len(text) <= 60) or LEVEL_RE.search(text):
                continue  # drop spot levels / RLs / coded annotations
            if len([w for w in text.split() if any(c.isalpha() for c in w)]) < 2:
                continue  # drop single codes/tokens (GM, USG, PP...)
            key = text.lower()
            if key not in by_text or size > by_text[key][1]:
                by_text[key] = (text, size)
    ranked = sorted(by_text.values(), key=lambda ts: -ts[1])
    return [text for text, _ in ranked[:cap]]


def format_manifest(manifest: list[PageFeatures]) -> str:
    return "\n".join(
        f"{p.pdf} p.{p.page}: {'; '.join(p.features)}" for p in manifest
    )
