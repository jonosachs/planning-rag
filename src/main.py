from src.llm import fetch_llm_response
from src.chunk import batch_chunk
from src.embed import batch_embed, embed_text
from src.ui import get_user_query, show_llm_response
from src.vector_db import (
    delete_db_collection_if_exists,
    get_records_from_db,
    write_to_db,
    query_db,
)
from src.ingest import run_fetch_scheme_pipeline
from src.io import write_json

scheme_title = "Port Phillip"
key_word = "shadow"
db_name = "planning_scheme"
delete_existing_db = False
write_chunks_to_file = True


def seed_db():
    print("⌛️ Getting scheme data..")
    scheme_clauses = run_fetch_scheme_pipeline(
        scheme_title, key_word=key_word, max_results=100
    )

    print("⌛️ Chunking..")
    chunks = batch_chunk(scheme_clauses)

    if write_chunks_to_file:
        # Write chunks to file in case of failure later in the pipeline
        write_json(chunks, "chunks.json")

    print("⌛️ Embedding chunks..")
    embedded_chunks = batch_embed(chunks)

    if delete_existing_db:
        print(f"⌛️ Deleting db {db_name}..")
        delete_db_collection_if_exists(db_name)

    print(f"⌛️ Writing to db {db_name}..")
    write_to_db(db_name, embedded_chunks)

    db_record_ids = get_records_from_db(db_name)
    n = len(db_record_ids)
    print(f"✅ DB seeded with {n} chunks..")


def run(query: str | None = None, num_results: int = 5):
    if not query:
        query = get_user_query()

    embedded_query = embed_text(query)
    context = query_db(db_name, embedded_query, num_results)
    response = fetch_llm_response(query, context)

    show_llm_response(response)


if __name__ == ("__main__"):
    run()
