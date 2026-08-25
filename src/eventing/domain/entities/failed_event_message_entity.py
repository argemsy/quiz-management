import uuid
from dataclasses import dataclass, field
from datetime import datetime

from src.eventing.shared.eventing_enums import FailedEventStatus


@dataclass(frozen=True)
class FailedEventMessageEntity:
    channel_path: str
    handler_path: str
    resource_name: str
    correlation_id: uuid.UUID
    error_message: str
    error_type: str
    status: FailedEventStatus
    created_at: datetime
    updated_at: datetime
    id: uuid.UUID | None = None
    retry_count: int = 0
    payload: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        channel_path: str,
        handler_path: str,
        resource_name: str,
        correlation_id: uuid.UUID,
        payload: dict | None = None,
        metadata: dict | None = None,
        error_type: str,
        error_message: str,
    ):

        now = datetime.now()

        return cls(
            id=uuid.uuid4(),
            channel_path=channel_path,
            handler_path=handler_path,
            resource_name=resource_name,
            correlation_id=correlation_id,
            payload=payload or dict(),
            metadata=metadata or dict(),
            error_type=error_type,
            error_message=error_message,
            status=FailedEventStatus.PENDING,
            retry_count=0,
            created_at=now,
            updated_at=now,
        )
