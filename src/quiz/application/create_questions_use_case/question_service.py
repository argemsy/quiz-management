import uuid

from src.quiz.domain.entities.question_entity import QuestionEntity
from src.quiz.domain.repositories.question_repository import QuestionRepository


class QuestionService:
    def __init__(self, repository: QuestionRepository) -> None:
        self.repository = repository

    async def create_questions(
        self,
        quiz_id: uuid.UUID,
        tenant: uuid.UUID,
        tenant_user: uuid.UUID,
        questions: list[QuestionEntity],
    ) -> list[QuestionEntity]:
        return await self.repository.bulk_create(
            quiz_id, tenant, tenant_user, questions
        )
