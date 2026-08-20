from src.eventing.application.record_audit_log_use_case.dto import RecordAuditLogDTO
from src.eventing.domain.entities.audit_log_entity import AuditLogEntity
from src.eventing.domain.repositories.audit_log_repository import AuditLogRepository


class RecordAuditLogUseCase:
    def __init__(self, repository: AuditLogRepository) -> None:
        self.repository = repository

    async def execute(self, dto: RecordAuditLogDTO) -> AuditLogEntity:
        entity = AuditLogEntity(
            object_id=dto.object_id,
            content_type=dto.content_type,
            source_type=dto.source_type,
            action_type=dto.action_type,
            object_repr=dto.object_repr,
            user=dto.user,
            tenant=dto.tenant,
            correlation_id=dto.correlation_id,
            metadata={
                "previous_state": dto.previous_state,
                "current_state": dto.current_state,
            },
        )
        return await self.repository.record(entity)
