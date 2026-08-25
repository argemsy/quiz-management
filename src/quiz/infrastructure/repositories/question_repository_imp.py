import uuid

from django.db import transaction

from src.quiz.domain.entities.question_entity import QuestionEntity
from src.quiz.domain.repositories.question_repository import QuestionRepository
from src.quiz.infrastructure.persistence.django.models import (
    AnswerChoiceModel,
    QuestionModel,
)
from src.shared.infrastructure.persistence.django.models import async_database


class QuestionRepositoryImpl(QuestionRepository):
    @async_database()
    def bulk_create(
        self,
        quiz_id: uuid.UUID,
        tenant: uuid.UUID,
        tenant_user: uuid.UUID,
        questions: list[QuestionEntity],
    ) -> list[QuestionEntity]:
        questions_to_create = []
        answers_to_create = []

        for question in questions:
            question_id = uuid.uuid4()

            questions_to_create.append(
                QuestionModel(
                    id=question_id,
                    text=question.text,
                    response_type=question.response_type.value,
                    quiz_id=quiz_id,
                    order=question.order,
                    tenant=tenant,
                    tenant_user=tenant_user,
                )
            )

            for choice in question.answer_choices:
                answers_to_create.append(
                    AnswerChoiceModel(
                        text=choice.text,
                        is_correct=choice.is_correct,
                        question_id=question_id,
                        order=choice.order,
                        tenant=tenant,
                        tenant_user=tenant_user,
                    )
                )

        with transaction.atomic():
            QuestionModel.objects.bulk_create(questions_to_create)
            AnswerChoiceModel.objects.bulk_create(answers_to_create)

        return [
            QuestionEntity(
                id=q.id,
                text=q.text,
                response_type=q.response_type,
                answer_choices=question.answer_choices,
                order=q.order,
            )
            for q, question in zip(questions_to_create, questions)
        ]
