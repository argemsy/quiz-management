import uuid

from pydantic import BaseModel, ConfigDict

from src.quiz.application.create_quiz_use_case.dto import QuestionDTO


class CreateQuestionsDTO(BaseModel):
    """Built by `handle_questions_requested` from a `QUESTIONS_REQUESTED`
    event's payload. Reuses `QuestionDTO` from `create_quiz_use_case` — same
    shape, no reason to redefine it."""

    model_config = ConfigDict(frozen=True)

    quiz_id: uuid.UUID
    tenant: uuid.UUID
    tenant_user: uuid.UUID
    questions: list[QuestionDTO]
