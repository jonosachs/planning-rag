from src.ingest import ClauseDoc
from dataclasses import dataclass


@dataclass
class MetaData:
    clause_id: str
    scheme_id: str
    semantic_number: str
    gazettal_date: str
    amendment_number: str
    title: str
    chunk_index: int


@dataclass
class Chunk:
    text: str
    metadata: MetaData


def batch_chunk(scheme_clauses: list[ClauseDoc]):
    chunks = []
    for clause in scheme_clauses:
        chunks.extend(chunk_clause(clause))
    return chunks


def chunk_clause(clause: ClauseDoc, max_chars: int = 750) -> list[Chunk]:
    chunks = []
    chunk_index = 0
    text = ""
    paragraphs = clause.content.split("\n")

    for p in paragraphs:
        combined = text + "\n" + p
        if len(combined) <= max_chars:
            text += p + "\n"
        else:
            chunk = Chunk(
                text=text.strip(),
                metadata=build_metadata(clause, chunk_index),
            )
            chunks.append(chunk)
            chunk_index += 1
            text = p + "\n"

    chunk = Chunk(
        text=text.strip(),
        metadata=build_metadata(clause, chunk_index),
    )
    chunks.append(chunk)

    return chunks


def build_metadata(cd: ClauseDoc, chunk_index):
    return MetaData(
        clause_id=cd.clause_id,
        scheme_id=cd.scheme_id,
        semantic_number=cd.semantic_number,
        gazettal_date=cd.gazettal_date,
        amendment_number=cd.amendment_number,
        title=cd.title,
        chunk_index=chunk_index,
    )
