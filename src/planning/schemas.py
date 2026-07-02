from pydantic import BaseModel


class ClauseRef(BaseModel):
    ordinance_id: str
    title: str
    scheme_id: str


class ClauseDoc(BaseModel):
    ordinance_id: str
    ordinance_type: str
    ordinance_level: str
    scheme_id: str
    gazettal_date: str
    amendment_number: str
    title: str
    content: str | None


class ClauseMetaData(BaseModel):
    ordinance_id: str
    ordinance_type: str
    ordinance_level: str
    scheme_id: str
    gazettal_date: str
    amendment_number: str
    title: str
    chunk_index: int
