from pydantic import BaseModel, Field
from typing import Optional


class PlanningCitation(BaseModel):
    scheme_id: str
    ordinance_id: str
    chunk_index: str
    title: str


class LlmPlanningResponse(BaseModel):
    answer: str = Field(
        description="Answer if it can be deduced from the context. Otherwise say you don't know."
    )
    citations: Optional[list[PlanningCitation]] = Field(
        description="""
        Citations for all context used in your answer. 
        Only 'None' if the answer is not in the context
        """,
        default=None,
    )


class ExtractedDwgField(BaseModel):
    value: float | str | None
    unit: str | None
    page: int
    bbox: tuple[float, float, float, float] | None
    source_text: str
    confidence: float


class DrawingFeature(BaseModel):
    address: ExtractedDwgField | None = None
    zone: ExtractedDwgField | None = None
    building_height_m: ExtractedDwgField | None = None
    front_setback_m: ExtractedDwgField | None = None
    side_setbacks_m: list[ExtractedDwgField] = Field(default_factory=list)
    rear_setback_m: ExtractedDwgField | None = None
    site_coverage_percent: ExtractedDwgField | None = None
    permeability_percent: ExtractedDwgField | None = None
    private_open_space_m2: ExtractedDwgField | None = None
