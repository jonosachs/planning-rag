"""Extract natural-ground RLs from a feature survey.

The survey carries existing/natural ground spot levels in AHD - the datum height
is measured from (elevations only show FFL/courtyard, not natural ground). This
pulls the AHD level pool; the model then reads the representative ground level
per orientation, since ground varies across the site.
"""

import re

import fitz

RL_RE = re.compile(r"^\d{1,3}\.\d{2,3}$")


def extract_ground_pool(page: fitz.Page, lo: float = 40.0, hi: float = 60.0) -> list[float]:
    """AHD-range level values (site ground ~50); excludes the low offsets/chainages."""
    values = set()
    for word in page.get_text("words"):
        text = word[4].strip()
        if RL_RE.match(text) and lo <= float(text) <= hi:
            values.add(float(text))
    return sorted(values)
