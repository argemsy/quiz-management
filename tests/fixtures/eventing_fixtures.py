import uuid
from dataclasses import replace as dataclasses_replace
from datetime import datetime
from enum import Enum, auto

import pytest

from src.eventing.domain.entities.audit_log_entity import AuditLogEntity
from src.eventing.domain.entities.failed_event_message_entity import (
    FailedEventMessageEntity,
)
from src.eventing.domain.exceptions import FailedEventMessageNotFoundError
from src.eventing.domain.repositories.audit_log_repository import AuditLogRepository
from src.eventing.domain.repositories.failed_event_message_repository import (
    FailedEventMessageRepository,
)
from src.eventing.infrastructure.repositories.failed_event_message_repository_imp import (
    FailedEventMessageRepositoryImpl,
)
from src.eventing.shared.eventing_enums import FailedEventStatus
from src.shared.infrastructure.event_bus import EventBusMessage


class SampleTestChannel(Enum):
    """Throwaway channel, used only to exercise the DLQ path in tests."""

    SOMETHING_HAPPENED = auto()


class FakeFailedEventMessageRepository(FailedEventMessageRepository):
    """In-memory stand-in for `FailedEventMessageRepositoryImpl`, used to unit
    test use-case orchestration without touching the database."""

    def __init__(self) -> None:
        self._rows: dict[uuid.UUID, FailedEventMessageEntity] = {}

    def save(self, entity: FailedEventMessageEntity) -> FailedEventMessageEntity:
        entity = entity if entity.id else _with_id(entity, uuid.uuid4())
        self._rows[entity.id] = entity
        return entity

    def get_by_id(self, id: uuid.UUID) -> FailedEventMessageEntity | None:
        return self._rows.get(id)

    def mark_resolved(self, id: uuid.UUID) -> FailedEventMessageEntity:
        entity = self._pending(id)
        updated = _replace(
            entity,
            status=FailedEventStatus.RESOLVED,
            retry_count=entity.retry_count + 1,
        )
        self._rows[id] = updated
        return updated

    def mark_retry_failed(
        self, id: uuid.UUID, error_type: str, error_message: str
    ) -> FailedEventMessageEntity:
        entity = self._pending(id)
        updated = _replace(
            entity,
            retry_count=entity.retry_count + 1,
            error_type=error_type,
            error_message=error_message,
        )
        self._rows[id] = updated
        return updated

    def _pending(self, id: uuid.UUID) -> FailedEventMessageEntity:
        entity = self._rows.get(id)
        if entity is None or entity.status != FailedEventStatus.PENDING:
            raise FailedEventMessageNotFoundError(id)
        return entity


class FakeAuditLogRepository(AuditLogRepository):
    """In-memory stand-in for `AuditLogRepositoryImpl`, used to unit test
    `RecordAuditLogUseCase` orchestration without touching the database."""

    def __init__(self) -> None:
        self.recorded: list[AuditLogEntity] = []

    async def record(self, entity: AuditLogEntity) -> AuditLogEntity:
        entity = entity if entity.id else dataclasses_replace(entity, id=uuid.uuid4())
        self.recorded.append(entity)
        return entity

    async def record_many(self, entities: list[AuditLogEntity]) -> list[AuditLogEntity]:
        return [await self.record(entity) for entity in entities]


def _with_id(
    entity: FailedEventMessageEntity, id: uuid.UUID
) -> FailedEventMessageEntity:
    return dataclasses_replace(entity, id=id)


def _replace(entity: FailedEventMessageEntity, **changes) -> FailedEventMessageEntity:
    return dataclasses_replace(entity, updated_at=datetime.now(), **changes)


@pytest.fixture
def sample_event_bus_message() -> EventBusMessage:
    return EventBusMessage(
        channel=SampleTestChannel.SOMETHING_HAPPENED,
        resource_name="create_tenant",
        data={"tenant_id": str(uuid.uuid4())},
        metadata={"user_id": str(uuid.uuid4())},
    )


def raising_sync_handler_fn(event: EventBusMessage) -> None:
    raise ValueError("sync handler exploded")


async def raising_async_handler_fn(event: EventBusMessage) -> None:
    raise ValueError("async handler exploded")


def succeeding_handler_fn(event: EventBusMessage) -> None:
    pass


# Module-level (not closures) so `RetryFailedEventUseCase`'s dotted-path
# resolution (importlib + getattr) can actually find them by handler_path.
@pytest.fixture
def raising_sync_handler():
    return raising_sync_handler_fn


@pytest.fixture
def raising_async_handler():
    return raising_async_handler_fn


@pytest.fixture
def succeeding_handler():
    return succeeding_handler_fn


@pytest.fixture
def fake_failed_event_message_repository() -> FakeFailedEventMessageRepository:
    return FakeFailedEventMessageRepository()


@pytest.fixture
def fake_audit_log_repository() -> FakeAuditLogRepository:
    return FakeAuditLogRepository()


@pytest.fixture
def failed_event_message_repository() -> FailedEventMessageRepositoryImpl:
    return FailedEventMessageRepositoryImpl()


@pytest.fixture
def failed_event_message(
    db, failed_event_message_repository: FailedEventMessageRepositoryImpl
) -> FailedEventMessageEntity:
    """A real, persisted `FailedEventMessage` row, for tests that need one to
    already exist (e.g. retry tests). Requires `@pytest.mark.django_db`."""
    entity = FailedEventMessageEntity.create(
        channel_path="tests.fixtures.eventing_fixtures:SampleTestChannel:SOMETHING_HAPPENED",
        handler_path="tests.fixtures.eventing_fixtures:raising_sync_handler_fn",
        resource_name="create_tenant",
        correlation_id=uuid.uuid4(),
        payload={"tenant_id": str(uuid.uuid4())},
        metadata={},
        error_type="ValueError",
        error_message="sync handler exploded",
    )
    return failed_event_message_repository.save(entity)
