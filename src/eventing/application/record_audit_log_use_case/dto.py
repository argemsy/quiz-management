import uuid

from pydantic import BaseModel, ConfigDict

from src.eventing.shared.eventing_enums import (
    AuditLogActionEnum,
    AuditLogContentTypeEnum,
    AuditLogSourceEnum,
)


class RecordAuditLogDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    object_id: uuid.UUID
    content_type: AuditLogContentTypeEnum
    source_type: AuditLogSourceEnum
    action_type: AuditLogActionEnum
    object_repr: str | None = None
    user: uuid.UUID | None = None
    tenant: uuid.UUID | None = None
    correlation_id: uuid.UUID | None = None
    previous_state: dict = {}
    current_state: dict = {}
