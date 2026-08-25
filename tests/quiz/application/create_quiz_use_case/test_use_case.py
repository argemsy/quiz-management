import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.quiz.application.create_quiz_use_case.dto import CreateQuizDTO
from src.quiz.application.create_quiz_use_case.quiz_service import QuizService
from src.quiz.application.create_quiz_use_case.tenant_validation_service import (
    TenantValidationService,
)
from src.quiz.application.create_quiz_use_case.use_case import CreateQuizUseCase
from src.quiz.shared.quiz_enums import QuizTypeEnum
from src.shared.application.idempotency_service import IdempotencyService
from src.shared.domain.exceptions import DuplicateOperationError


def _make_dto(**overrides) -> CreateQuizDTO:
    defaults = dict(
        tenant_id=uuid.uuid4(),
        tenant_user_id=uuid.uuid4(),
        quiz_type=QuizTypeEnum.PRACTICE,
        configuration={},
        questions=[],
        correlation_id=str(uuid.uuid4()),
        operation_id=str(uuid.uuid4()),
    )
    defaults.update(overrides)
    return CreateQuizDTO(**defaults)


def _make_use_case(idempotency_service: IdempotencyService) -> CreateQuizUseCase:
    quiz_service = MagicMock(spec=QuizService)
    tenant_validation_service = MagicMock(spec=TenantValidationService)
    tenant_validation_service.ensure_tenant_and_membership = AsyncMock(
        return_value=None
    )
    event_bus = MagicMock()
    use_case = CreateQuizUseCase(
        quiz_service, tenant_validation_service, event_bus, idempotency_service
    )
    return use_case, event_bus


@pytest.mark.asyncio
async def test_event_bus_is_not_published_to_when_idempotency_service_run_raises():
    """`execute()` has no decorator and no try/except (see design.md -
    Decisions, use-case-service-boundary) — the guard against publishing a
    `QUESTIONS_REQUESTED` event for a Quiz that was never actually created
    relies entirely on `IdempotencyService.run` raising instead of
    returning a sentinel, which unwinds `execute()` before it ever reaches
    `event_bus.publish(...)`."""
    idempotency_service = MagicMock(spec=IdempotencyService)
    idempotency_service.run = AsyncMock(side_effect=RuntimeError("write failed"))
    use_case, event_bus = _make_use_case(idempotency_service)

    with pytest.raises(RuntimeError):
        await use_case.execute(_make_dto())

    event_bus.publish.assert_not_called()
    idempotency_service.mark_success.assert_not_called()


@pytest.mark.asyncio
async def test_event_bus_is_not_published_to_on_a_duplicate_operation_id():
    idempotency_service = MagicMock(spec=IdempotencyService)
    idempotency_service.run = AsyncMock(
        side_effect=DuplicateOperationError(
            operation_id="op-1", status="SUCCEEDED", response_payload={}
        )
    )
    use_case, event_bus = _make_use_case(idempotency_service)

    with pytest.raises(DuplicateOperationError):
        await use_case.execute(_make_dto())

    event_bus.publish.assert_not_called()
