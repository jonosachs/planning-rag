from abc import ABC, abstractmethod
from pydantic import BaseModel


class Llm(ABC):
    @abstractmethod
    def get_response(self, sys_prompt: str, data: str) -> BaseModel:
        raise NotImplementedError
