import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict

from src.quiz.shared.quiz_enums import QuestionResponseTypeEnum, QuizTypeEnum
from src.shared.application.dto import CorrelationIdDTO, OperationIdDTO


class AnswerChoiceDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    is_correct: bool


class QuestionDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    response_type: QuestionResponseTypeEnum
    answer_choices: list[AnswerChoiceDTO]


class CreateQuizDTO(CorrelationIdDTO, OperationIdDTO):
    """Validated input for `CreateQuizUseCase`. Built by the GraphQL resolver
    from `CreateQuizInput` — kept free of any strawberry/presentation import
    so the application layer doesn't depend on it. Carries `correlation_id`
    (propagated to `EventBusMessage`) and `operation_id` (idempotency key
    for `IdempotencyService`) since this is the only use case with both."""

    model_config = ConfigDict(frozen=True)

    tenant_id: uuid.UUID
    tenant_user_id: uuid.UUID
    quiz_type: QuizTypeEnum
    configuration: dict[str, Any]
    questions: list[QuestionDTO]
