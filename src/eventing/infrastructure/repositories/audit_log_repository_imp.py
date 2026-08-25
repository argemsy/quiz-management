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

    @async_database()
    def record_many(self, entities: list[AuditLogEntity]) -> list[AuditLogEntity]:
        """Batched counterpart to `record()` — a bulk admin action (e.g.
        soft-delete across a 100k-row selection) must not turn into one
        INSERT per object; `bulk_create` keeps it to one query per
        `batch_size` chunk. `id` is pre-generated per object, same reason
        as `QuestionRepositoryImpl.bulk_create` — an INSERT needs it
        upfront, `bulk_create` doesn't assign PKs back for a UUID PK.
        `created_at`/`updated_at` are left for Django's own
        `auto_now_add`/`auto_now` handling, same as that example does.
        """
        models = [
            AuditLog(
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
            for entity in entities
        ]
        AuditLog.objects.bulk_create(models, batch_size=1000)
        return [AuditLogEntity.from_model(model) for model in models]
