from src.quiz.application.create_quiz_use_case.dto import CreateQuizDTO
from src.quiz.application.create_quiz_use_case.quiz_service import QuizService
from src.quiz.application.create_quiz_use_case.tenant_validation_service import (
    TenantValidationService,
)
from src.quiz.domain.entities.question_entity import AnswerChoiceEntity, QuestionEntity
from src.quiz.domain.entities.quiz_entity import QuizEntity
from src.quiz.shared.quiz_event_channels import QuizEventChannel
from src.shared.application.idempotency_service import IdempotencyService
from src.shared.infrastructure.event_bus import EventBus, EventBusMessage
from src.shared.infrastructure.logging import LogDomain, get_logger

logger = get_logger(LogDomain.QUIZ)


class CreateQuizUseCase:
    """Orchestrator: validates the tenant/tenant_user through
    `TenantValidationService`, creates the Quiz through `QuizService` inside
    an idempotency-key reservation (see `IdempotencyService` — this is what
    actually prevents a duplicate `Quiz` row on a repeated `operation_id`,
    not the caller's Redis fast-path lock), then publishes a
    `QUESTIONS_REQUESTED` event so the questions are created by their own
    handler — decoupled from this request/response cycle. If that handler
    fails, the EventBus's failure sink persists it as a dead letter,
    retryable via `RetryFailedEventUseCase`.
    """

    def __init__(
        self,
        quiz_service: QuizService,
        tenant_validation_service: TenantValidationService,
        event_bus: EventBus,
        idempotency_service: IdempotencyService,
    ) -> None:
        self.quiz_service = quiz_service
        self.tenant_validation_service = tenant_validation_service
        self.event_bus = event_bus
        self.idempotency_service = idempotency_service

    async def execute(self, dto: CreateQuizDTO) -> QuizEntity:
        self._validate_questions(dto)

        await self.tenant_validation_service.ensure_tenant_and_membership(
            dto.tenant_id, dto.tenant_user_id
        )

        quiz_entity = self.quiz_service.build_entity(dto)
        quiz = await self.idempotency_service.run(
            dto.operation_id, lambda: self.quiz_service.save_sync(quiz_entity)
        )
        await self.idempotency_service.mark_success(
            dto.operation_id, {"quiz_id": str(quiz.id)}
        )

        self.event_bus.publish(
            EventBusMessage(
                channel=QuizEventChannel.QUESTIONS_REQUESTED,
                resource_name="create_questions",
                correlation_id=dto.correlation_id,
                data={
                    "quiz_id": str(quiz.id),
                    "tenant": str(quiz.tenant),
                    "tenant_user": str(quiz.tenant_user),
                    "questions": [
                        question.model_dump(mode="json") for question in dto.questions
                    ],
                },
            )
        )
        logger.info(
            "quiz_created",
            correlation_id=dto.correlation_id,
            quiz_id=str(quiz.id),
            questions_requested=len(dto.questions),
        )
        return quiz

    @staticmethod
    def _validate_questions(dto: CreateQuizDTO) -> None:
        """Builds throwaway domain entities purely to run their validation
        (e.g. a question needs >=1 answer choice) before anything else runs
        — invalid question data fails the whole mutation up front instead of
        leaving behind a Quiz whose QUESTIONS_REQUESTED event is doomed to
        keep failing."""
        for question in dto.questions:
            QuestionEntity(
                text=question.text,
                response_type=question.response_type,
                answer_choices=[
                    AnswerChoiceEntity(text=choice.text, is_correct=choice.is_correct)
                    for choice in question.answer_choices
                ],
            )
