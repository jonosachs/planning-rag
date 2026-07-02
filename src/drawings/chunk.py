from src.planning.schemas import ClauseDoc, ClauseMetaData
from src.indexing.schemas import Chunk


def batch_chunk(clause_docs: list[ClauseDoc]):
    output = []
    for clause in clause_docs:
        chunks = chunk_clause(clause)
        if chunks:
            output.extend(chunks)
    return output


def chunk_clause(clause: ClauseDoc, max_chars: int = 750) -> list[Chunk] | None:
    if not clause.content:
        return None

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


def build_metadata(cd: ClauseDoc, chunk_index) -> dict:
    return ClauseMetaData(
        ordinance_id=cd.ordinance_id,
        ordinance_type=cd.ordinance_type,
        ordinance_level=cd.ordinance_level,
        scheme_id=cd.scheme_id,
        gazettal_date=cd.gazettal_date,
        amendment_number=cd.amendment_number,
        title=cd.title,
        chunk_index=chunk_index,
    )
