import uuid

from src.eventing.application.record_audit_log_use_case.dto import RecordAuditLogDTO
from src.eventing.domain.entities.audit_log_entity import AuditLogEntity
from src.eventing.domain.repositories.audit_log_repository import AuditLogRepository


class RecordAuditLogUseCase:
    def __init__(self, repository: AuditLogRepository) -> None:
        self.repository = repository

    async def execute(self, dto: RecordAuditLogDTO) -> AuditLogEntity:
        return await self.repository.record(self._to_entity(dto))

    async def execute_many(self, dtos: list[RecordAuditLogDTO]) -> list[AuditLogEntity]:
        """Batched counterpart to `execute()` — a bulk admin action publishes
        one event carrying many records instead of one event per record, so
        the write side records them with one `bulk_create()` instead of N
        single-row inserts."""
        return await self.repository.record_many([self._to_entity(dto) for dto in dtos])

    @staticmethod
    def _to_entity(dto: RecordAuditLogDTO) -> AuditLogEntity:
        return AuditLogEntity(
            object_id=dto.object_id,
            content_type=dto.content_type,
            source_type=dto.source_type,
            action_type=dto.action_type,
            object_repr=dto.object_repr,
            user=dto.user,
            tenant=dto.tenant,
            # `RecordAuditLogDTO.correlation_id` is `str` (the codebase-wide
            # transport convention, matching `Context`/`EventBusMessage`);
            # `AuditLogEntity.correlation_id` is `uuid.UUID` (matches the
            # domain modeling and `from_model`'s read path from the DB) —
            # this is the one parse point between the two conventions.
            correlation_id=uuid.UUID(dto.correlation_id),
            metadata={
                "previous_state": dto.previous_state,
                "current_state": dto.current_state,
            },
        )
