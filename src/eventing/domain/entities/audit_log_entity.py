import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.eventing.shared.eventing_enums import (
    AuditLogActionEnum,
    AuditLogContentTypeEnum,
    AuditLogSourceEnum,
)


@dataclass(frozen=True)
class AuditLogEntity:
    object_id: uuid.UUID
    content_type: AuditLogContentTypeEnum
    source_type: AuditLogSourceEnum
    action_type: AuditLogActionEnum
    id: uuid.UUID | None = None
    object_repr: str | None = None
    user: uuid.UUID | None = None
    tenant: uuid.UUID | None = None
    correlation_id: uuid.UUID | None = None
    metadata: dict = field(
        default_factory=lambda: {"previous_state": {}, "current_state": {}}
    )
    created_at: datetime | None = None

    @classmethod
    def from_model(cls, instance: Any) -> "AuditLogEntity":
        return cls(
            id=instance.id,
            object_id=instance.object_id,
            object_repr=instance.object_repr,
            user=instance.user,
            tenant=instance.tenant,
            correlation_id=instance.correlation_id,
            content_type=AuditLogContentTypeEnum(instance.content_type),
            source_type=AuditLogSourceEnum(instance.source_type),
            action_type=AuditLogActionEnum(instance.action_type),
            metadata=instance.metadata or {},
            created_at=instance.created_at,
        )
