from src.quiz.application.create_quiz_use_case.dto import CreateQuizDTO
from src.quiz.domain.entities.quiz_entity import QuizConfiguration, QuizEntity
from src.quiz.domain.repositories.quiz_repository import QuizRepository


class QuizService:
    def __init__(self, repository: QuizRepository) -> None:
        self.repository = repository

    def build_entity(self, dto: CreateQuizDTO) -> QuizEntity:
        return QuizEntity(
            quiz_type=dto.quiz_type,
            tenant=dto.tenant_id,
            tenant_user=dto.tenant_user_id,
            configuration=QuizConfiguration(**dto.configuration),
        )

    async def create_quiz(self, dto: CreateQuizDTO) -> QuizEntity:
        return await self.repository.create(self.build_entity(dto))

    def save_sync(self, quiz: QuizEntity) -> QuizEntity:
        """Sync counterpart to `create_quiz`, for composing into another
        transaction — see `QuizRepository.save_sync`."""
        return self.repository.save_sync(quiz)
