from src.indexing.interfaces import DataSource, Embedder, VectorStore


def run_indexing_pipeline(source: DataSource, embedder: Embedder, store: VectorStore):
    data = source.load()
    chunks = source.chunk(data)
    embedded_chunks = embedder.embed_chunks(chunks)
    store.write(embedded_chunks)

    n = len(store.get_all()["ids"])
    print(f"✅ DB seeded with {n} chunks..")
