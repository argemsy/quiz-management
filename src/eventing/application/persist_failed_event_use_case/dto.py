import json
import uuid
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder
from pydantic import BaseModel, ConfigDict, field_validator

from src.shared.infrastructure.event_bus import EventBusHandler, EventBusMessage


class PersistFailedEventDTO(BaseModel):
    """Validated input for `PersistFailedEventUseCase`. `from_event_bus_failure`
    is the one place that knows how to drain an `EventBusMessage` failure
    (event, handler, exception) into these fields."""

    model_config = ConfigDict(frozen=True)

    channel_path: str
    handler_path: str
    resource_name: str
    correlation_id: uuid.UUID
    payload: Any = None
    metadata: Any = None
    error_type: str
    error_message: str

    @field_validator("payload", "metadata", mode="before")
    @classmethod
    def _coerce_json_safe(cls, value: Any) -> Any:
        """Best-effort JSON coercion — a dead letter shouldn't fail to save
        just because the payload isn't plain-JSON (e.g. a Django model
        instance)."""
        try:
            json.dumps(value, cls=DjangoJSONEncoder)
            return value
        except TypeError:
            return {"__unserializable__": repr(value)}

    @classmethod
    def from_event_bus_failure(
        cls, event: EventBusMessage, handler: EventBusHandler, exc: Exception
    ) -> "PersistFailedEventDTO":
        return cls(
            channel_path=cls._channel_path(event),
            handler_path=cls._handler_path(handler),
            resource_name=event.resource_name,
            correlation_id=event.correlation_id,
            payload=event.data,
            metadata=event.metadata,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )

    @staticmethod
    def _channel_path(event: EventBusMessage) -> str:
        channel_cls = type(event.channel)
        return (
            f"{channel_cls.__module__}:{channel_cls.__qualname__}:{event.channel.name}"
        )

    @staticmethod
    def _handler_path(handler: EventBusHandler) -> str:
        return (
            f"{handler.__module__}:{getattr(handler, '__qualname__', handler.__name__)}"
        )
