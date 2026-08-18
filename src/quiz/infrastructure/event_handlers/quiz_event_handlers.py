from src.quiz.application.create_questions_use_case.dto import CreateQuestionsDTO
from src.quiz.application.create_questions_use_case.question_service import (
    QuestionService,
)
from src.quiz.application.create_questions_use_case.use_case import (
    CreateQuestionsUseCase,
)
from src.quiz.infrastructure.repositories.question_repository_imp import (
    QuestionRepositoryImpl,
)
from src.shared.infrastructure.event_bus import EventBusMessage


async def handle_questions_requested(event: EventBusMessage) -> None:
    """Subscribed to `QuizEventChannel.QUESTIONS_REQUESTED` in
    `QuizConfig.ready()`. A failure here is caught by the EventBus and
    persisted as a dead letter (see `EventingConfig.ready()`), retryable via
    `RetryFailedEventUseCase` — this handler doesn't need its own retry logic.
    """
    dto = CreateQuestionsDTO(
        quiz_id=event.data["quiz_id"],
        tenant=event.data["tenant"],
        tenant_user=event.data["tenant_user"],
        questions=event.data["questions"],
    )
    use_case = CreateQuestionsUseCase(QuestionService(QuestionRepositoryImpl()))
    await use_case.execute(dto)
