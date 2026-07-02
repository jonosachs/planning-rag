from pydantic import BaseModel


class Chunk(BaseModel):
    text: str
    metadata: dict


class EmbeddedChunk(BaseModel):
    text: str
    metadata: dict
    embedded_text: list[float]
