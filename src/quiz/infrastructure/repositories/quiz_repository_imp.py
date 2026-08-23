import uuid

from src.quiz.domain.entities.quiz_entity import QuizEntity
from src.quiz.domain.repositories.quiz_repository import QuizRepository
from src.quiz.infrastructure.persistence.django.models import QuizModel
from src.shared.infrastructure.persistence.django.models import async_database


class QuizRepositoryImpl(QuizRepository):
    @async_database()
    def create(self, quiz: QuizEntity) -> QuizEntity:
        return self.save_sync(quiz)

    def save_sync(self, quiz: QuizEntity) -> QuizEntity:
        quiz_model = QuizModel.objects.create(
            quiz_type=quiz.quiz_type.value,
            configuration=quiz.configuration.to_primitive(),
            tenant=quiz.tenant,
            tenant_user=quiz.tenant_user,
        )
        return QuizEntity.from_model(quiz_model)

    @async_database()
    def get_by_id(self, quiz_id: uuid.UUID) -> QuizEntity | None:
        quiz_model = QuizModel.objects.filter(id=quiz_id).first()
        return QuizEntity.from_model(quiz_model) if quiz_model else None
