from src.eventing.application.record_audit_log_use_case.dto import RecordAuditLogDTO
from src.eventing.application.record_audit_log_use_case.use_case import (
    RecordAuditLogUseCase,
)
from src.eventing.infrastructure.repositories.audit_log_repository_imp import (
    AuditLogRepositoryImpl,
)
from src.shared.infrastructure.event_bus import EventBusMessage


async def handle_account_entity_changed(event: EventBusMessage) -> None:
    """Subscribed to `AccountEventChannel.ENTITY_CHANGED` in
    `EventingConfig.ready()`. A failure here is caught by the EventBus and
    persisted as a dead letter, retryable via `RetryFailedEventUseCase` —
    this handler doesn't need its own retry logic.
    """
    dto = RecordAuditLogDTO(
        object_id=event.data["object_id"],
        content_type=event.data["content_type"],
        source_type=event.data["source_type"],
        action_type=event.data["action_type"],
        object_repr=event.data.get("object_repr"),
        user=event.data.get("user"),
        tenant=event.data.get("tenant"),
        correlation_id=event.correlation_id,
        previous_state=event.data.get("previous_state", {}),
        current_state=event.data.get("current_state", {}),
    )
    use_case = RecordAuditLogUseCase(AuditLogRepositoryImpl())
    await use_case.execute(dto)
