from abc import ABC, abstractmethod
from pydantic import BaseModel
from src.query.prompt import Prompt


class Llm(ABC):
    @abstractmethod
    def get_response(self, prompt: Prompt) -> BaseModel:
        raise NotImplementedError
