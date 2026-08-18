from src.eventing.application.persist_failed_event_use_case.dto import (
    PersistFailedEventDTO,
)
from src.shared.infrastructure.event_bus import EventBusMessage
from tests.fixtures.eventing_fixtures import SampleTestChannel


def test_from_event_bus_failure_extracts_sync_handler_path(
    sample_event_bus_message: EventBusMessage, raising_sync_handler
):
    dto = PersistFailedEventDTO.from_event_bus_failure(
        sample_event_bus_message, raising_sync_handler, ValueError("boom")
    )

    assert dto.channel_path == (
        f"{SampleTestChannel.__module__}:SampleTestChannel:SOMETHING_HAPPENED"
    )
    assert dto.handler_path.endswith("raising_sync_handler_fn")
    assert dto.error_type == "ValueError"
    assert dto.error_message == "boom"


def test_from_event_bus_failure_extracts_async_handler_path(
    sample_event_bus_message: EventBusMessage, raising_async_handler
):
    dto = PersistFailedEventDTO.from_event_bus_failure(
        sample_event_bus_message, raising_async_handler, ValueError("boom")
    )

    assert dto.handler_path.endswith("raising_async_handler_fn")


def test_from_event_bus_failure_coerces_unserializable_payload(raising_sync_handler):
    class Unserializable:
        pass

    event = EventBusMessage(
        channel=SampleTestChannel.SOMETHING_HAPPENED,
        resource_name="create_tenant",
        data=Unserializable(),
    )

    dto = PersistFailedEventDTO.from_event_bus_failure(
        event, raising_sync_handler, ValueError("boom")
    )

    assert isinstance(dto.payload, dict)
    assert "__unserializable__" in dto.payload
