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
        questions = [
            QuestionEntity(
                text=question.text,
                response_type=question.response_type,
                answer_choices=[
                    AnswerChoiceEntity(text=choice.text, is_correct=choice.is_correct)
                    for choice in question.answer_choices
                ],
            )
            for question in dto.questions
        ]

        created = await self.question_service.create_questions(
            dto.quiz_id, dto.tenant, dto.tenant_user, questions
        )
        logger.info(
            "questions_created",
            quiz_id=str(dto.quiz_id),
            questions_created=len(created),
        )
        return created
