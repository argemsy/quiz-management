import uuid
from enum import Enum, auto

import pytest

from src.eventing.application.retry_failed_event_use_case.dto import RetryFailedEventDTO
from src.eventing.application.retry_failed_event_use_case.use_case import (
    RetryFailedEventUseCase,
)
from src.eventing.infrastructure.persistence.django.models import FailedEventMessage
from src.eventing.infrastructure.repositories.failed_event_message_repository_imp import (
    FailedEventMessageRepositoryImpl,
)
from src.eventing.shared.eventing_enums import FailedEventStatus
from src.shared.infrastructure.event_bus import EventBusMessage, get_event_bus

pytestmark = pytest.mark.django_db


class E2EChannel(Enum):
    """Throwaway channel, only used to exercise the real EventBus -> DLQ ->
    retry path end to end."""

    TENANT_CREATED = auto()


def _e2e_handler(event: EventBusMessage) -> None:
    if _e2e_handler.should_fail:
        raise RuntimeError("still broken")


_e2e_handler.should_fail = True


def test_publish_failure_persists_a_dead_letter_row_and_retry_resolves_it():
    """Exercises the actual wiring set up in `EventingConfig.ready()`: a
    handler failure on the real `EventBus` singleton must land as a
    `FailedEventMessage` row via `PersistFailedEventUseCase`, and
    `RetryFailedEventUseCase` must be able to resolve it once the handler
    is fixed."""
    _e2e_handler.should_fail = True
    bus = get_event_bus()
    bus.subscribe(E2EChannel.TENANT_CREATED, _e2e_handler)

    correlation_id = str(uuid.uuid4())
    bus.publish(
        EventBusMessage(
            channel=E2EChannel.TENANT_CREATED,
            resource_name="create_tenant",
            correlation_id=correlation_id,
            data={"tenant_id": "abc"},
        )
    )

    row = FailedEventMessage.objects.get(correlation_id=correlation_id)
    assert row.status == FailedEventStatus.PENDING.value

    _e2e_handler.should_fail = False
    use_case = RetryFailedEventUseCase(FailedEventMessageRepositoryImpl())
    result = use_case.execute(RetryFailedEventDTO(failed_event_id=row.id))

    assert result.status == FailedEventStatus.RESOLVED
    assert result.retry_count == 1
