from src.planning.schemas import ClauseDoc, ClauseMetaData
from src.indexing.schemas import Chunk


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


def chunk_clause(clause: ClauseDoc, max_chars: int = 750) -> list[Chunk]:
    """Break clause text into chunks with metadata"""

    if not clause.content:
        return []

    # Include section and parent header in each chunk to retain context when embedded
    header = get_header(clause)

    chunks = []
    text_bucket = ""

    for paragraph in clause.content.split("\n"):
        text_bucket += paragraph + "\n"
        # Allow overshooting max chars. Ignore header length
        if len(text_bucket) >= max_chars:
            chunks.append(
                Chunk(
                    text=add_header(header, text_bucket),
                    metadata=build_metadata(clause, len(chunks)),
                )
            )
            text_bucket = ""

    # Capture any left-over text
    if text_bucket.strip():
        chunk = Chunk(
            text=add_header(header, text_bucket),
            metadata=build_metadata(clause, len(chunks)),
        )
        chunks.append(chunk)

    return chunks


def get_header(clause: ClauseDoc) -> str:
    header = ""
    if clause.section:
        header += f"{clause.section.strip()}\n"
    if clause.parent_title:
        header += f"{clause.parent_title.strip()}\n"
    return header


def add_header(header, text):
    return f"{header.strip()}\n{text.strip()}" if header else text.strip()


def build_metadata(clause: ClauseDoc, chunk_index: int) -> dict:
    return ClauseMetaData(
        # Exclude content as it's already stored in Chroma's 'documents' field
        **clause.model_dump(exclude={"content"}),
        chunk_index=chunk_index,
    ).model_dump()
