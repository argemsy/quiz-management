import uuid

from src.eventing.application.persist_failed_event_use_case.dto import (
    PersistFailedEventDTO,
)
from src.eventing.application.persist_failed_event_use_case.use_case import (
    PersistFailedEventUseCase,
)
from src.eventing.shared.eventing_enums import FailedEventStatus
from tests.fixtures.eventing_fixtures import FakeFailedEventMessageRepository


def test_execute_saves_an_entity_matching_the_dto():
    repository = FakeFailedEventMessageRepository()
    use_case = PersistFailedEventUseCase(repository)
    dto = PersistFailedEventDTO(
        channel_path="module:Channel:MEMBER",
        handler_path="module:handler",
        resource_name="create_tenant",
        correlation_id=uuid.uuid4(),
        payload={"tenant_id": "abc"},
        metadata={"user_id": "def"},
        error_type="ValueError",
        error_message="boom",
    )

    saved = use_case.execute(dto)

    assert saved.channel_path == dto.channel_path
    assert saved.handler_path == dto.handler_path
    assert saved.correlation_id == dto.correlation_id
    assert saved.payload == dto.payload
    assert saved.metadata == dto.metadata
    assert saved.error_type == dto.error_type
    assert saved.error_message == dto.error_message
    assert saved.status == FailedEventStatus.PENDING
    assert repository.get_by_id(saved.id) == saved
