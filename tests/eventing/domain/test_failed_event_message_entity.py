import uuid

from src.eventing.domain.entities.failed_event_message_entity import (
    FailedEventMessageEntity,
)
from src.eventing.shared.eventing_enums import FailedEventStatus


def test_create_sets_pending_status_and_zero_retry_count():
    entity = FailedEventMessageEntity.create(
        channel_path="module:Channel:MEMBER",
        handler_path="module:handler",
        resource_name="create_tenant",
        correlation_id=uuid.uuid4(),
        error_type="ValueError",
        error_message="boom",
    )

    assert entity.status == FailedEventStatus.PENDING
    assert entity.retry_count == 0


def test_create_generates_an_id():
    entity = FailedEventMessageEntity.create(
        channel_path="module:Channel:MEMBER",
        handler_path="module:handler",
        resource_name="create_tenant",
        correlation_id=uuid.uuid4(),
        error_type="ValueError",
        error_message="boom",
    )

    assert isinstance(entity.id, uuid.UUID)


def test_create_sets_matching_created_and_updated_timestamps():
    entity = FailedEventMessageEntity.create(
        channel_path="module:Channel:MEMBER",
        handler_path="module:handler",
        resource_name="create_tenant",
        correlation_id=uuid.uuid4(),
        error_type="ValueError",
        error_message="boom",
    )

    assert entity.created_at == entity.updated_at


def test_create_defaults_payload_and_metadata_to_empty_dicts():
    entity = FailedEventMessageEntity.create(
        channel_path="module:Channel:MEMBER",
        handler_path="module:handler",
        resource_name="create_tenant",
        correlation_id=uuid.uuid4(),
        error_type="ValueError",
        error_message="boom",
    )

    assert entity.payload == {}
    assert entity.metadata == {}
