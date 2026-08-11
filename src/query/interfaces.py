from abc import ABC, abstractmethod

from src.query.schemas import PlanningCitation


class UserInterface(ABC):
    @abstractmethod
    def get_user_query(self) -> str:
        pass

    @abstractmethod
    def show_cited_response(
        self, answer: str, cited: dict[str, list[PlanningCitation]]
    ) -> None:
        pass
