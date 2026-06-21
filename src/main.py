from src.llm import fetch_llm_response
from src.chunk import batch_chunk
from src.embed import batch_embed, embed_text
from src.vector_db import (
    delete_db_collection,
    get_records_from_db,
    write_to_db,
    query_db,
)
from src.ingest import run_fetch_scheme_pipeline
import sys


db_name = "melb_planning_regs_sample"


def seed_db():
    print("⌛️ Getting scheme data..")
    # TODO: ommit schedules
    scheme_clauses = run_fetch_scheme_pipeline("Melbourne")

    print("⌛️ Chunking..")
    chunks = batch_chunk(scheme_clauses)

    print("⌛️ Embedding chunks..")
    embedded_chunks = batch_embed(chunks)

    print("⌛️ Delete previous db..")
    delete_db_collection(db_name)

    print("⌛️ Writing to new db..")
    write_to_db(db_name, embedded_chunks)

    db_record_ids = get_records_from_db(db_name)
    n = len(db_record_ids)
    print(f"✅ DB seeded with {n} records..")


def run(query: str | None = None, num_results: int = 5):
    if not query:
        query = sys.argv[1]

    embedded_query = embed_text(query)
    context = query_db(db_name, embedded_query, num_results)

    llm_response = fetch_llm_response(query, context)
    print(llm_response)


if __name__ == ("__main__"):
    run()
