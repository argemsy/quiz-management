import uuid

import strawberry

from src.account.infrastructure.repositories import TenantLookupRepositoryImpl
from src.eventing.infrastructure.repositories import (
    idempotency_reservation_repository_imp as idempotency_repo_imp,
)
from src.quiz.application.create_quiz_use_case.dto import CreateQuizDTO
from src.quiz.application.create_quiz_use_case.quiz_service import QuizService
from src.quiz.application.create_quiz_use_case.tenant_validation_service import (
    TenantValidationService,
)
from src.quiz.application.create_quiz_use_case.use_case import CreateQuizUseCase
from src.quiz.infrastructure.repositories.quiz_repository_imp import QuizRepositoryImpl
from src.quiz.presentation.schema.inputs.create_quiz_input import CreateQuizInput
from src.quiz.presentation.schema.responses.create_quiz_response import (
    CreateQuizPayload,
    CreateQuizResponse,
)
from src.quiz.presentation.schema.types.quiz_type import QuizType
from src.shared.application.idempotency_service import IdempotencyService
from src.shared.domain.exceptions import DuplicateOperationError
from src.shared.domain.repositories.idempotency_reservation_repository import (
    IdempotencyOutcome,
)
from src.shared.infrastructure.event_bus import get_event_bus
from src.shared.presentation.decorators import handle_mutations_exceptions
from src.shared.presentation.schema.context import Info
from src.shared.presentation.schema.permissions import IsStaff
from src.shared.presentation.schema.responses import (
    IntegrityErrorResponse,
    ValidationErrorResponse,
)


@strawberry.type
class QuizAdminMutation:

    @strawberry.mutation(permission_classes=[IsStaff])
    @handle_mutations_exceptions
    async def create_quiz(
        self, info: Info, input: CreateQuizInput
    ) -> CreateQuizResponse:
        correlation_id = info.context.correlation_id
        operation_id = info.context.operation_id
        # `strawberry.asdict` mirrors `CreateQuizInput`'s shape exactly, so
        # the nested `quiz` field's contents (quiz_type/configuration/
        # questions) must be lifted to the top level to match
        # `CreateQuizDTO` — pre-existing bug found while adding idempotency
        # here: `create_quiz` had never been exercised end-to-end via
        # GraphQL (no prior test caught it).
        input_kwargs = strawberry.asdict(input)
        quiz_kwargs = input_kwargs.pop("quiz")
        dto = CreateQuizDTO.model_validate(
            {
                **input_kwargs,
                **quiz_kwargs,
                "correlation_id": correlation_id,
                "operation_id": operation_id,
            }
        )
        quiz_repository = QuizRepositoryImpl()
        use_case = CreateQuizUseCase(
            QuizService(quiz_repository),
            TenantValidationService(TenantLookupRepositoryImpl()),
            get_event_bus(),
            IdempotencyService(
                idempotency_repo_imp.IdempotencyReservationRepositoryImpl()
            ),
        )
        try:
            quiz_entity = await use_case.execute(dto)
        except DuplicateOperationError as exc:
            return await self._replay_create_quiz(correlation_id, quiz_repository, exc)

        return CreateQuizPayload(
            correlation_id=correlation_id,
            payload=QuizType(value=quiz_entity),
        )

    @staticmethod
    async def _replay_create_quiz(
        correlation_id: str,
        quiz_repository: QuizRepositoryImpl,
        exc: DuplicateOperationError,
    ) -> CreateQuizResponse:
        """A repeated `operation_id` was already reserved by a prior
        `create_quiz` attempt — reconstructed here (not generically in
        `@handle_mutations_exceptions`) by re-fetching the `Quiz` that
        attempt created, since `CreateQuizPayload` wraps a domain entity
        that can't be safely rebuilt from a naive JSON round-trip (see
        design.md - Decisions, mutation-idempotency-rate-limit)."""
        if exc.status == IdempotencyOutcome.SUCCEEDED.value and exc.response_payload:
            quiz_entity = await quiz_repository.get_by_id(
                uuid.UUID(exc.response_payload["quiz_id"])
            )
            if quiz_entity is not None:
                return CreateQuizPayload(
                    correlation_id=correlation_id,
                    payload=QuizType(value=quiz_entity),
                )

        if exc.status == IdempotencyOutcome.FAILED_TERMINAL.value:
            return ValidationErrorResponse(
                correlation_id=correlation_id,
                message="This operation already failed and cannot be retried.",
                field=None,
            )

        return IntegrityErrorResponse(
            correlation_id=correlation_id,
            message=(
                "A request with this operation_id is already being "
                "processed; retry shortly."
            ),
        )
