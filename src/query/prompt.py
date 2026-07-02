from src.indexing.interfaces import Embedder, VectorStore


system_prompt = """
    You are answering questions about Victorian planning schemes.
    Use only the context below. If the answer is not in the context, say you do not know.
    If context contains site-specific, schedule-specific, or location-specific controls, identify them as specific controls and do not present them as general requirements.
    If the question asks for high-level requirements, prefer VPP clauses and general provisions over schedules.
    """


def package_prompt(user_query, context):
    prompt = f"{system_prompt}\nUser query:{user_query}\nContext: {context}"
    return prompt


def build_prompt_with_context(
    query: str, embedder: Embedder, store: VectorStore
) -> str:
    embedded_query = embedder.embed_text(query)
    context = store.run_query(embedded_query)
    prompt = package_prompt(query, context)
    return prompt
