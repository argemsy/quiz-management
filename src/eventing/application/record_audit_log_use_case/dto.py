import uuid

from pydantic import ConfigDict

from src.eventing.shared.eventing_enums import (
    AuditLogActionEnum,
    AuditLogContentTypeEnum,
    AuditLogSourceEnum,
)
from src.shared.application.dto import CorrelationIdDTO


class RecordAuditLogDTO(CorrelationIdDTO):
    """`correlation_id` inherited from `CorrelationIdDTO` (`str`, required)
    instead of an ad-hoc `uuid.UUID | None` field — every caller
    (`audit_event_handlers.py`) always supplies `EventBusMessage.
    correlation_id`, which is never `None` (the bus's `default_factory`
    guarantees a value), so the old `| None` was unused defensiveness."""

    model_config = ConfigDict(frozen=True)

    object_id: uuid.UUID
    content_type: AuditLogContentTypeEnum
    source_type: AuditLogSourceEnum
    action_type: AuditLogActionEnum
    object_repr: str | None = None
    user: uuid.UUID | None = None
    tenant: uuid.UUID | None = None
    previous_state: dict = {}
    current_state: dict = {}
