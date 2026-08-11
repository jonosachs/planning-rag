from pydantic import BaseModel


class ClauseRef(BaseModel):
    ordinance_id: str
    title: str
    section: str | None
    scheme_id: str


class ClauseFields(BaseModel):
    ordinance_id: str
    ordinance_type: str
    ordinance_level: str
    scheme_id: str
    semantic_num: str
    gazettal_date: str
    amendment_number: str
    title: str
    section: str = ""  # Chroma can't store None so use empty string
    parent_ordinance_id: str = ""
    parent_title: str = ""


class ClauseDoc(ClauseFields):
    content: str | None


class ClauseMetaData(ClauseFields):
    chunk_index: int
