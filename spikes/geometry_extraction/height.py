"""Cross-drawing building height: elevation tops - survey natural ground (AHD).

Elevations give ridge / wall-top RLs; the feature survey gives natural ground per
orientation; AHD links them. Ground varies across the site, so setback
requirements are computed as a RANGE and the verdict flags "marginal" when it is
sensitive to which ground spot is used. Code does the arithmetic; the model only
identifies which RL is which.
"""

from dataclasses import dataclass, field

import fitz

from spikes.geometry_extraction.elevation import extract_levels
from spikes.geometry_extraction.survey import extract_ground_pool
from spikes.geometry_extraction.vision import identify_ground_levels, identify_levels

WALL_THRESHOLD_M = 3.6  # ResCode: side/rear setback = 1m + 0.3m per m of wall over 3.6m


@dataclass
class HeightFacts:
    ridge_rl: float | None
    wall_top_rl: float | None
    ground: dict[str, float | None]
    ground_min: float | None
    ground_max: float | None
    overall_height_m: float | None  # ridge - lowest ground (worst case)


def building_height_facts(elevations_pdf: str, survey_pdf: str, elev_page: int = 1) -> HeightFacts:
    ep = fitz.open(elevations_pdf)[elev_page]
    epool = sorted({lvl.rl for lvl in extract_levels(ep)})
    ep.get_pixmap(matrix=fitz.Matrix(2.5, 2.5), alpha=False).save("tmp/h_elev.png")
    ident = identify_levels("tmp/h_elev.png", epool)
    ridge = ident.ridge_rl if ident.ridge_rl in epool else None
    wall_top = ident.top_of_wall_rl if ident.top_of_wall_rl in epool else None

    sp = fitz.open(survey_pdf)[0]
    spool = extract_ground_pool(sp)
    sp.get_pixmap(matrix=fitz.Matrix(3, 3), alpha=False).save("tmp/h_survey.png")
    g = identify_ground_levels("tmp/h_survey.png", spool)
    ground = {o: (v if v in spool else None) for o, v in (
        ("front", g.front_ground_rl), ("rear", g.rear_ground_rl),
        ("north", g.north_ground_rl), ("south", g.south_ground_rl))}

    gv = [v for v in ground.values() if v is not None]
    gmin, gmax = (min(gv), max(gv)) if gv else (None, None)
    overall = round(ridge - gmin, 2) if ridge is not None and gmin is not None else None
    return HeightFacts(ridge, wall_top, ground, gmin, gmax, overall)


def required_setback_range_m(wall_top: float | None, ground_low: float | None,
                             ground_high: float | None) -> tuple[float, float] | None:
    """ResCode side/rear setback range from wall-top RL and the local ground range."""
    if wall_top is None or ground_low is None or ground_high is None:
        return None
    def req(wall_h: float) -> float:
        return round(1 + 0.3 * max(0.0, wall_h - WALL_THRESHOLD_M), 3)
    return req(wall_top - ground_high), req(wall_top - ground_low)  # (smaller h, larger h)


def setback_verdict(provided_m: float, req_range: tuple[float, float] | None) -> str:
    if req_range is None:
        return "undetermined"
    lo, hi = req_range
    if provided_m >= hi:
        return "complies"
    if provided_m < lo:
        return "does not comply"
    return "marginal (verdict sensitive to ground level - survey confirmation needed)"
