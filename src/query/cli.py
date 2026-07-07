from src.query.schemas import LlmPlanningResponse
from src.query.interfaces import UserInterface


class Cli(UserInterface):
    def __init__(self):
        pass

    def show_cited_response(self, response: LlmPlanningResponse):
        print(f"\nAnswer: {response.answer}\n")

        if hasattr(response, "planning_citations"):
            self._print_citations("Planning citations", response.planning_citations)
            self._print_citations("Drawing citations", response.drawing_citations)
            return

        self._print_citations("Citations", response.citations or [])

    def _print_citations(self, heading, citations):
        print(f"{heading}:")

        if not citations:
            print("None")
            return

        for count, citation in enumerate(citations):
            citation_text = [
                f"{key}: {value}" for key, value in citation.model_dump().items()
            ]
            print(f"{count + 1} {citation_text}")

    def get_user_query(self):
        query = input("\nQuery: ")
        return query.strip()
