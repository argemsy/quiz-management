import uuid
from abc import ABC, abstractmethod

from src.quiz.domain.entities.question_entity import QuestionEntity


class QuestionRepository(ABC):
    @abstractmethod
    async def bulk_create(
        self,
        quiz_id: uuid.UUID,
        tenant: uuid.UUID,
        tenant_user: uuid.UUID,
        questions: list[QuestionEntity],
    ) -> list[QuestionEntity]:
        pass
