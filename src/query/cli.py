from src.query.schemas import LlmPlanningResponse
from src.query.interfaces import UserInterface


class Cli(UserInterface):
    def __init__(self):
        pass

    def show_cited_response(self, response: LlmPlanningResponse):
        print(f"\nAnswer: {response.answer}\n")
        print("Citations:")

        for count, citation in enumerate(response.citations):
            citation_text = [
                f"{key}: {value}" for key, value in citation.model_dump().items()
            ]
            print(f"{count + 1} {citation_text}")

    def get_user_query(self):
        query = input("\nQuery: ")
        return query.strip()
