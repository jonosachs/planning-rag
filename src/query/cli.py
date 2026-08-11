from src.query.interfaces import UserInterface
from src.query.schemas import PlanningCitation


class Cli(UserInterface):
    def __init__(self):
        pass

    def show_cited_response(
        self, answer: str, cited: dict[str, list[PlanningCitation]]
    ):
        output = [f"\nAnswer: {answer}"]
        output.append(
            "\nCitations (parent_title : title : ordinance_id : chunk_index):"
        )

        for section, members in cited.items():
            heading = self._truncate(section)
            output.append(heading)
            output.extend(
                f"  - {self._truncate(m.parent_title)} : {self._truncate(m.title)} : {m.ordinance_id} : {m.chunk_index}"
                for m in members
            )

        print("\n".join(output))

    @staticmethod
    def _truncate(text: str, max_chars: int = 75) -> str:
        return f"{text[:max_chars].strip()}..." if len(text) > max_chars else text

    def get_user_query(self):
        query = input("\nQuery: ")
        return query.strip()
