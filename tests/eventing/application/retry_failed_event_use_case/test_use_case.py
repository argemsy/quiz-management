import uuid

import pytest

from src.eventing.application.retry_failed_event_use_case.dto import RetryFailedEventDTO
from src.eventing.application.retry_failed_event_use_case.use_case import (
    RetryFailedEventUseCase,
)
from src.eventing.domain.entities.failed_event_message_entity import (
    FailedEventMessageEntity,
)
from src.eventing.domain.exceptions import FailedEventMessageNotFoundError
from src.eventing.shared.eventing_enums import FailedEventStatus
from tests.fixtures import eventing_fixtures
from tests.fixtures.eventing_fixtures import FakeFailedEventMessageRepository


def _seed_failed_event(
    repository: FakeFailedEventMessageRepository, *, handler_path: str
) -> FailedEventMessageEntity:
    entity = FailedEventMessageEntity.create(
        channel_path="tests.fixtures.eventing_fixtures:SampleTestChannel:SOMETHING_HAPPENED",
        handler_path=handler_path,
        resource_name="create_tenant",
        correlation_id=uuid.uuid4(),
        payload={"tenant_id": "abc"},
        metadata={},
        error_type="ValueError",
        error_message="sync handler exploded",
    )
    return repository.save(entity)


def test_execute_marks_resolved_when_the_handler_now_succeeds(monkeypatch):
    monkeypatch.setattr(
        eventing_fixtures,
        "raising_sync_handler_fn",
        eventing_fixtures.succeeding_handler_fn,
    )
    repository = FakeFailedEventMessageRepository()
    seeded = _seed_failed_event(
        repository,
        handler_path="tests.fixtures.eventing_fixtures:raising_sync_handler_fn",
    )
    use_case = RetryFailedEventUseCase(repository)

    result = use_case.execute(RetryFailedEventDTO(failed_event_id=seeded.id))

    assert result.status == FailedEventStatus.RESOLVED
    assert result.retry_count == 1


def test_execute_marks_retry_failed_and_reraises_when_the_handler_still_fails():
    repository = FakeFailedEventMessageRepository()
    seeded = _seed_failed_event(
        repository,
        handler_path="tests.fixtures.eventing_fixtures:raising_sync_handler_fn",
    )
    use_case = RetryFailedEventUseCase(repository)

    with pytest.raises(ValueError, match="sync handler exploded"):
        use_case.execute(RetryFailedEventDTO(failed_event_id=seeded.id))

    updated = repository.get_by_id(seeded.id)
    assert updated.status == FailedEventStatus.PENDING
    assert updated.retry_count == 1
    assert updated.error_type == "ValueError"


def test_execute_raises_not_found_error_for_unknown_id():
    repository = FakeFailedEventMessageRepository()
    use_case = RetryFailedEventUseCase(repository)

    with pytest.raises(FailedEventMessageNotFoundError):
        use_case.execute(RetryFailedEventDTO(failed_event_id=uuid.uuid4()))
