from pydantic import BaseModel, Field


class PdfTextFeature(BaseModel):
    page: int
    text: str
    bbox: tuple[float, float, float, float]
    block_no: int
    block_type: int


class PageFeautres(BaseModel):
    page: int
    img_path: str
    text_features: list[PdfTextFeature]


class DrawingFact(BaseModel):
    fact_type: str
    value: str | None = None
    unit: str | None = None
    element: str | None = None
    status: str | None = None
    original_pdf_page: int
    image_path: str | None = None
    sheet_number: str | None = None
    sheet_title: str | None = None
    evidence: str
    confidence: str
    caveat: str | None = None


class DrawingPageFacts(BaseModel):
    original_pdf_page: int
    image_path: str
    sheet_number: str | None = None
    sheet_title: str | None = None
    facts: list[DrawingFact]
    notes: list[str] = Field(default_factory=list)


class DrawingFactsResponse(BaseModel):
    project_type: str | None = None
    site_address: str | None = None
    zoning_or_overlay_notes: list[str] = Field(default_factory=list)
    pages: list[DrawingPageFacts]
    overall_caveats: list[str] = Field(default_factory=list)


class DrawingEvidenceFact(BaseModel):
    original_pdf_page: int
    image_path: str | None = None
    sheet_number: str | None = None
    sheet_title: str | None = None
    fact_type: str
    finding: str
    value: str | None = None
    unit: str | None = None
    element: str | None = None
    status: str | None = None
    evidence: str
    confidence: str
    caveat: str | None = None
    endpoint_a: str | None = None
    endpoint_b: str | None = None
    nearby_labels: list[str] = Field(default_factory=list)
    validation_status: str = "unvalidated"
    validation_reason: str | None = None


class DrawingEvidenceResponse(BaseModel):
    question: str
    relevant_pages: list[int]
    facts: list[DrawingEvidenceFact]
    summary: str
    caveats: list[str] = Field(default_factory=list)
