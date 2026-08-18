from src.quiz.application.create_quiz_use_case.dto import CreateQuizDTO
from src.quiz.domain.entities.quiz_entity import QuizConfiguration, QuizEntity
from src.quiz.domain.repositories.quiz_repository import QuizRepository


class QuizService:
    def __init__(self, repository: QuizRepository) -> None:
        self.repository = repository

    async def create_quiz(self, dto: CreateQuizDTO) -> QuizEntity:
        quiz = QuizEntity(
            quiz_type=dto.quiz_type,
            tenant=dto.tenant_id,
            tenant_user=dto.tenant_user_id,
            configuration=QuizConfiguration(**dto.configuration),
        )
        return await self.repository.create(quiz)
