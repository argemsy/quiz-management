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

    `AuditableAdminMixin` publishes two payload shapes on this same
    channel: a single flat record (`save_model` — always exactly one
    object) and a batch (`data["records"]`, from a bulk admin action —
    routed to `execute_many()` so N affected objects become one
    `bulk_create()` instead of N single-row inserts).
    """
    use_case = RecordAuditLogUseCase(AuditLogRepositoryImpl())
    records = event.data.get("records")
    if records is not None:
        dtos = [_to_dto(record, event.correlation_id) for record in records]
        await use_case.execute_many(dtos)
        return

    await use_case.execute(_to_dto(event.data, event.correlation_id))


def _to_dto(data: dict, correlation_id) -> RecordAuditLogDTO:
    return RecordAuditLogDTO(
        object_id=data["object_id"],
        content_type=data["content_type"],
        source_type=data["source_type"],
        action_type=data["action_type"],
        object_repr=data.get("object_repr"),
        user=data.get("user"),
        tenant=data.get("tenant"),
        correlation_id=correlation_id,
        previous_state=data.get("previous_state", {}),
        current_state=data.get("current_state", {}),
    )
