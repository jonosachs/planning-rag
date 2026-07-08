"""Extract building height from an elevation: RL pool -> model IDs -> compute.

Code extracts the RL pool; the model identifies ridge / natural ground / wall-top
from that pool + the image; code cross-checks each against the pool and computes
overall height (ridge - natural ground) and wall height (top-of-wall - natural
ground).

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_height
"""

import fitz

from spikes.geometry_extraction.elevation import extract_levels
from spikes.geometry_extraction.vision import identify_levels

SAMPLE_PDF = "assets/elevations_and_sections.pdf"
PAGE = 1  # page 2 - has ridge/eaves/natural ground


def main() -> None:
    page = fitz.open(SAMPLE_PDF)[PAGE]
    levels = extract_levels(page)
    pool = sorted({l.rl for l in levels})
    print(f"RL pool ({len(pool)}): {pool}\n")

    crop = "tmp/height_elev.png"
    page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5), alpha=False).save(crop)
    ident = identify_levels(crop, pool)

    ridge = confirm(ident.ridge_rl, pool)
    ground = confirm(ident.natural_ground_rl, pool)
    wall_top = confirm(ident.top_of_wall_rl, pool)
    print(f"ridge_rl:          {ridge}")
    print(f"natural_ground_rl: {ground}")
    print(f"top_of_wall_rl:    {wall_top}")
    print(f"reasoning: {ident.reasoning[:160]}\n")

    if ridge and ground:
        print(f"overall building height = {ridge} - {ground} = {round(ridge - ground, 2)} m")
    if wall_top and ground:
        wall_h = round(wall_top - ground, 2)
        req = round(1 + 0.3 * max(0, wall_h - 3.6), 2)
        print(f"wall height = {wall_top} - {ground} = {wall_h} m "
              f"-> ResCode side/rear setback required ~{req} m")


def confirm(value, pool) -> float | None:
    """Trust the model's RL only if it's actually in the extracted pool."""
    return value if value in pool else None


if __name__ == "__main__":
    main()
