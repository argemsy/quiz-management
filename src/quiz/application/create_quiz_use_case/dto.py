import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict

from src.quiz.shared.quiz_enums import QuestionResponseTypeEnum, QuizTypeEnum


class AnswerChoiceDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    is_correct: bool


class QuestionDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    response_type: QuestionResponseTypeEnum
    answer_choices: list[AnswerChoiceDTO]


class CreateQuizDTO(BaseModel):
    """Validated input for `CreateQuizUseCase`. Built by the GraphQL resolver
    from `CreateQuizInput` — kept free of any strawberry/presentation import
    so the application layer doesn't depend on it."""

    model_config = ConfigDict(frozen=True)

    tenant_id: uuid.UUID
    tenant_user_id: uuid.UUID
    quiz_type: QuizTypeEnum
    configuration: dict[str, Any]
    questions: list[QuestionDTO]
