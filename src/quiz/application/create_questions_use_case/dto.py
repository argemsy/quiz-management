import uuid

from pydantic import ConfigDict

from src.quiz.application.create_quiz_use_case.dto import QuestionDTO
from src.shared.application.dto import CorrelationIdDTO


class CreateQuestionsDTO(CorrelationIdDTO):
    """Built by `handle_questions_requested` from a `QUESTIONS_REQUESTED`
    event's payload. Reuses `QuestionDTO` from `create_quiz_use_case` — same
    shape, no reason to redefine it. Carries `correlation_id` from
    `EventBusMessage.correlation_id` so the trace chain from `create_quiz`
    through to `questions_created` isn't lost."""

    model_config = ConfigDict(frozen=True)

    quiz_id: uuid.UUID
    tenant: uuid.UUID
    tenant_user: uuid.UUID
    questions: list[QuestionDTO]
