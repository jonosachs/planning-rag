from pydantic import BaseModel, Field, computed_field
from typing import Optional


class PlanningCitation(BaseModel):
    # Ordered index number for the result (0-based indexing).
    # Allows LLM to identify an int index rather than recreate the citation label which is error prone
    citation_index: int
    citation_id: str
    scheme_id: str
    ordinance_id: str
    semantic_num: str
    chunk_index: int
    title: str
    content: str

    @computed_field
    @property
    def label(self) -> str:
        return f"{self.citation_id} - {self.title}"


class LlmPlanningResponse(BaseModel):
    answer: str = Field(
        description="Answer if it can be deduced from the context. Otherwise say you don't know."
    )
    citation_idxs: Optional[list[int]] = Field(
        description="List the indicies of citations used in your response. Only 'None' if the answer is not in the context",
        default=None,
    )
