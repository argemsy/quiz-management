import uuid

import pytest

from src.eventing.domain.entities.failed_event_message_entity import (
    FailedEventMessageEntity,
)
from src.eventing.domain.exceptions import FailedEventMessageNotFoundError
from src.eventing.infrastructure.repositories.failed_event_message_repository_imp import (
    FailedEventMessageRepositoryImpl,
)
from src.eventing.shared.eventing_enums import FailedEventStatus

pytestmark = pytest.mark.django_db


def _new_entity(**overrides) -> FailedEventMessageEntity:
    return FailedEventMessageEntity.create(
        channel_path="module:Channel:MEMBER",
        handler_path="module:handler",
        resource_name="create_tenant",
        correlation_id=uuid.uuid4(),
        payload={"tenant_id": "abc"},
        metadata={"user_id": "def"},
        error_type="ValueError",
        error_message="boom",
        **overrides,
    )


def test_save_persists_and_round_trips_through_get_by_id():
    repository = FailedEventMessageRepositoryImpl()
    saved = repository.save(_new_entity())

    fetched = repository.get_by_id(saved.id)

    assert fetched is not None
    assert fetched.id == saved.id
    assert fetched.channel_path == "module:Channel:MEMBER"
    assert fetched.status == FailedEventStatus.PENDING


def test_get_by_id_returns_none_for_missing_id():
    repository = FailedEventMessageRepositoryImpl()

    assert repository.get_by_id(uuid.uuid4()) is None


def test_mark_resolved_sets_status_and_bumps_retry_count():
    repository = FailedEventMessageRepositoryImpl()
    saved = repository.save(_new_entity())

    resolved = repository.mark_resolved(saved.id)

    assert resolved.status == FailedEventStatus.RESOLVED
    assert resolved.retry_count == 1


def test_mark_retry_failed_updates_error_and_leaves_status_pending():
    repository = FailedEventMessageRepositoryImpl()
    saved = repository.save(_new_entity())

    updated = repository.mark_retry_failed(
        saved.id, error_type="TypeError", error_message="still broken"
    )

    assert updated.status == FailedEventStatus.PENDING
    assert updated.retry_count == 1
    assert updated.error_type == "TypeError"
    assert updated.error_message == "still broken"


def test_mark_resolved_raises_not_found_for_unknown_id():
    repository = FailedEventMessageRepositoryImpl()

    with pytest.raises(FailedEventMessageNotFoundError):
        repository.mark_resolved(uuid.uuid4())


def test_mark_retry_failed_raises_not_found_for_unknown_id():
    repository = FailedEventMessageRepositoryImpl()

    with pytest.raises(FailedEventMessageNotFoundError):
        repository.mark_retry_failed(
            uuid.uuid4(), error_type="TypeError", error_message="x"
        )


def test_mark_resolved_called_twice_raises_not_found_on_the_second_call():
    repository = FailedEventMessageRepositoryImpl()
    saved = repository.save(_new_entity())

    repository.mark_resolved(saved.id)

    with pytest.raises(FailedEventMessageNotFoundError):
        repository.mark_resolved(saved.id)


def test_mark_retry_failed_after_mark_resolved_raises_not_found():
    repository = FailedEventMessageRepositoryImpl()
    saved = repository.save(_new_entity())

    repository.mark_resolved(saved.id)

    with pytest.raises(FailedEventMessageNotFoundError):
        repository.mark_retry_failed(
            saved.id, error_type="TypeError", error_message="x"
        )
