from src.planning.schemas import ClauseChunk, ClauseDoc, ClauseMetaData
from src.rag.schemas import Chunk


def batch_chunk(clause_docs: list[ClauseDoc]):
    output = []
    for clause in clause_docs:
        if clause.content:
            chunks = chunk_clause(clause)
            output.extend(chunks)
            print(
                f"Clause {clause.title} {clause.ordinance_id} -> {len(chunks)} chunks"
            )

    return output


def chunk_clause(clause: ClauseDoc, max_chars: int = 750) -> list[ClauseChunk]:
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
