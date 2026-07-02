from src.drawings.schemas import PageFeautres
from src.drawings.pipeline import extract_drawing_data
from src.drawings.chunk import batch_chunk
from src.indexing.interfaces import DataSource
from src.indexing.schemas import Chunk


class DrawingsSource(DataSource):
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path

    def load(self) -> list[PageFeautres]:
        features = extract_drawing_data(self.pdf_path)
        return features

    def chunk(self, items) -> list[Chunk]:
        chunks = batch_chunk(items)
        return chunks
