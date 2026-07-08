"""Cross-drawing building height: elevations + survey -> facts + required setback.

Run from repo root:
    .venv/bin/python -m spikes.geometry_extraction.run_building_height
"""

from spikes.geometry_extraction.height import (
    building_height_facts,
    required_setback_range_m,
    setback_verdict,
)

ELEVATIONS = "assets/elevations_and_sections.pdf"
SURVEY = "assets/feature_survey.pdf"
SOUTH_SIDE_PROVIDED_M = 1.03  # from the setback pipeline


def main() -> None:
    h = building_height_facts(ELEVATIONS, SURVEY)
    print(f"ridge RL:     {h.ridge_rl} AHD")
    print(f"wall-top RL:  {h.wall_top_rl} AHD")
    print(f"ground/side:  {h.ground}")
    print(f"ground range: {h.ground_min}..{h.ground_max} AHD")
    print(f"overall height (ridge - lowest ground) = {h.overall_height_m} m\n")

    rng = required_setback_range_m(h.wall_top_rl, h.ground_min, h.ground_max)
    print(f"side/rear required setback range: {rng} m")
    if rng:
        print(f"south side provided {SOUTH_SIDE_PROVIDED_M} m -> "
              f"{setback_verdict(SOUTH_SIDE_PROVIDED_M, rng)}")


if __name__ == "__main__":
    main()
