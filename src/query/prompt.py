from src.query.schemas import PlanningCitation
from dataclasses import dataclass

SYSTEM_PROMPT = """
You are answering questions about Victorian planning schemes.
Use only the context below. If the answer is not in the context, say you do not know.
If context contains site-specific, schedule-specific, or location-specific controls, identify them as specific controls and do not present them as general requirements.
If the question asks for high-level requirements, prefer VPP clauses and general provisions over schedules.
"""


@dataclass
class Prompt:
    system_prompt: str
    contents: str


def build_llm_prompt(user_query: str, citations: list[PlanningCitation]) -> Prompt:
    contents = f"User query: {user_query}"

    if citations:
        cit_labels = []
        for idx, ctn in enumerate(citations):
            # 0-based indexing for prompt
            c = f"{idx} - {ctn.title}\n{ctn.content}"
            cit_labels.append(c)

        contents += f"\nContext:\n{'\n\n'.join(cit_labels)}\n"

    return Prompt(system_prompt=SYSTEM_PROMPT, contents=contents)
