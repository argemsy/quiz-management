from src.quiz.application.create_questions_use_case.dto import CreateQuestionsDTO
from src.quiz.application.create_questions_use_case.question_service import (
    QuestionService,
)
from src.quiz.domain.entities.question_entity import AnswerChoiceEntity, QuestionEntity
from src.shared.infrastructure.logging import LogDomain, get_logger

logger = get_logger(LogDomain.QUIZ)


class CreateQuestionsUseCase:
    def __init__(self, question_service: QuestionService) -> None:
        self.question_service = question_service

    async def execute(self, dto: CreateQuestionsDTO) -> list[QuestionEntity]:
        # Positions are derived from the submitted sequence rather than
        # carried on the DTO: the list is already the author's intent, and a
        # second source of truth for the same fact would only raise questions
        # (conflicting? sparse? tied?) that nothing needs to answer. The
        # `start=1` density guarantee originates here.
        questions = [
            QuestionEntity(
                text=question.text,
                response_type=question.response_type,
                order=position,
                answer_choices=[
                    AnswerChoiceEntity(
                        text=choice.text,
                        is_correct=choice.is_correct,
                        order=choice_position,
                    )
                    for choice_position, choice in enumerate(
                        question.answer_choices, start=1
                    )
                ],
            )
            for position, question in enumerate(dto.questions, start=1)
        ]

        created = await self.question_service.create_questions(
            dto.quiz_id, dto.tenant, dto.tenant_user, questions
        )
        logger.info(
            "questions_created",
            correlation_id=dto.correlation_id,
            quiz_id=str(dto.quiz_id),
            questions_created=len(created),
        )
        return created
