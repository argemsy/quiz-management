from abc import ABC, abstractmethod

from src.eventing.domain.entities.audit_log_entity import AuditLogEntity


class AuditLogRepository(ABC):
    @abstractmethod
    async def record(self, entity: AuditLogEntity) -> AuditLogEntity:
        pass

    @abstractmethod
    async def record_many(self, entities: list[AuditLogEntity]) -> list[AuditLogEntity]:
        pass
