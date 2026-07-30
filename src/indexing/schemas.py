from pydantic import BaseModel

from src.planning.schemas import ClauseMetaData


class Chunk(BaseModel):
    text: str
    metadata: ClauseMetaData | dict


class EmbeddedChunk(BaseModel):
    text: str
    metadata: ClauseMetaData | dict
    embedded_text: list[float]
