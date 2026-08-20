import uuid

from src.eventing.domain.entities.audit_log_entity import AuditLogEntity
from src.eventing.domain.repositories.audit_log_repository import AuditLogRepository
from src.eventing.infrastructure.persistence.django.models import AuditLog
from src.shared.infrastructure.persistence.django.models import async_database


class AuditLogRepositoryImpl(AuditLogRepository):
    @async_database()
    def record(self, entity: AuditLogEntity) -> AuditLogEntity:
        model = AuditLog.objects.create(
            id=entity.id or uuid.uuid4(),
            object_id=entity.object_id,
            object_repr=entity.object_repr,
            user=entity.user,
            tenant=entity.tenant,
            correlation_id=entity.correlation_id,
            content_type=entity.content_type.value,
            source_type=entity.source_type.value,
            action_type=entity.action_type.value,
            metadata=entity.metadata,
        )
        return AuditLogEntity.from_model(model)
