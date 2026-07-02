from abc import ABC, abstractmethod


class UserInterface(ABC):
    @abstractmethod
    def get_user_query(self) -> str:
        pass

    @abstractmethod
    def show_cited_response(self, response) -> None:
        pass
