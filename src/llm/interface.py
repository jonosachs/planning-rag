from abc import ABC, abstractmethod
from pydantic import BaseModel
from dataclasses import dataclass


@dataclass
class Prompt:
    system_prompt: str
    contents: str


class Llm(ABC):
    @abstractmethod
    def get_response(self, prompt: Prompt) -> BaseModel:
        raise NotImplementedError
