import uuid
from unittest.mock import AsyncMock, patch

import pytest

from src.quiz.infrastructure.event_handlers.quiz_event_handlers import (
    handle_questions_requested,
)
from src.quiz.shared.quiz_event_channels import QuizEventChannel
from src.shared.infrastructure.event_bus import EventBusMessage


@pytest.mark.asyncio
async def test_handle_questions_requested_propagates_the_event_correlation_id():
    """`event.correlation_id` must reach `CreateQuestionsDTO`, closing the
    trace chain from `create_quiz` through to `questions_created` — see
    use-case-service-boundary proposal.md - Why."""
    correlation_id = str(uuid.uuid4())
    event = EventBusMessage(
        channel=QuizEventChannel.QUESTIONS_REQUESTED,
        resource_name="create_questions",
        correlation_id=correlation_id,
        data={
            "quiz_id": str(uuid.uuid4()),
            "tenant": str(uuid.uuid4()),
            "tenant_user": str(uuid.uuid4()),
            "questions": [],
        },
    )

    target = (
        "src.quiz.infrastructure.event_handlers.quiz_event_handlers."
        "CreateQuestionsUseCase"
    )
    with patch(target) as MockUseCase:
        MockUseCase.return_value.execute = AsyncMock(return_value=[])

        await handle_questions_requested(event)

        dto = MockUseCase.return_value.execute.call_args.args[0]
        assert dto.correlation_id == correlation_id
