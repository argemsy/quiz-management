import uuid
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Generic, Optional, TypeVar

ModelT = TypeVar("ModelT")
MetadataT = TypeVar("MetadataT")


@dataclass(frozen=True)
class EventBusMessage(Generic[ModelT, MetadataT]):
    """
    Immutable message envelope for Event Bus communication.

    Attributes:
        channel: The destination channel/topic for this message. Each bounded
            context defines its own channel Enum (e.g. an ``AuditEventChannel``
            under ``src/<app>/shared/``) instead of sharing one global enum.
        resource_name: Human-readable identifier for the origin/resource tied
            to this event (e.g. "create_tenant").
        correlation_id: Ties every message produced while handling the same
            request/operation together, including messages a handler emits
            in reaction to this one (e.g. an audit-log entry published in
            response to a "tenant created" event). Pass one in explicitly to
            propagate an existing trace (e.g. a request-scoped trace id);
            otherwise a new UUID4 is generated automatically.
        data: The event payload. Defaults to None.
        metadata: Auxiliary context (user_id, trace_id, etc). Defaults to {}.
    """

    channel: Enum
    resource_name: str
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    data: Optional[ModelT] = None
    metadata: MetadataT = field(default_factory=dict)

    def success(
        self, data: ModelT, metadata: MetadataT
    ) -> "EventBusMessage[ModelT, MetadataT]":
        return replace(self, data=data, metadata=metadata)

    def failure(self, metadata: MetadataT) -> "EventBusMessage[ModelT, MetadataT]":
        return replace(self, metadata=metadata)
