from pydantic import BaseModel


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
