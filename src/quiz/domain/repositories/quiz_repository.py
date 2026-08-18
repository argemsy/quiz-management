from abc import ABC, abstractmethod

from src.quiz.domain.entities.quiz_entity import QuizEntity


class QuizRepository(ABC):
    @abstractmethod
    async def create(self, quiz: QuizEntity) -> QuizEntity:
        pass
