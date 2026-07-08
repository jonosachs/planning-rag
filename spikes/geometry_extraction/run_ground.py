"""Extract natural ground level per orientation from the feature survey.

Ground truth spot checks: front 50.12, rear 50.60, north 50.53, south 50.39.

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_ground
"""

import fitz

from spikes.geometry_extraction.survey import extract_ground_pool
from spikes.geometry_extraction.vision import identify_ground_levels

SAMPLE_PDF = "assets/feature_survey.pdf"
CROP = "tmp/survey.png"


def main() -> None:
    page = fitz.open(SAMPLE_PDF)[0]
    pool = extract_ground_pool(page)
    print(f"AHD ground pool ({len(pool)}): {pool}\n")

    page.get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False).save(CROP)
    g = identify_ground_levels(CROP, pool)

    for name, val in (("front", g.front_ground_rl), ("rear", g.rear_ground_rl),
                      ("north", g.north_ground_rl), ("south", g.south_ground_rl)):
        certified = val if val in pool else None
        print(f"  {name:5} ground RL: {certified}")
    print(f"\nreasoning: {g.reasoning[:200]}")


if __name__ == "__main__":
    main()
