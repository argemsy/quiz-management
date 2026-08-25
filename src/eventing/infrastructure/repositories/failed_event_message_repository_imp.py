import uuid

from django.db import transaction

from src.eventing.domain.entities.failed_event_message_entity import (
    FailedEventMessageEntity,
)
from src.eventing.domain.exceptions import FailedEventMessageNotFoundError
from src.eventing.domain.repositories.failed_event_message_repository import (
    FailedEventMessageRepository,
)
from src.eventing.infrastructure.persistence.django.models import FailedEventMessage
from src.eventing.shared.eventing_enums import FailedEventStatus


class FailedEventMessageRepositoryImpl(FailedEventMessageRepository):
    def save(self, entity: FailedEventMessageEntity) -> FailedEventMessageEntity:
        model = FailedEventMessage.objects.create(
            id=entity.id or uuid.uuid4(),
            channel_path=entity.channel_path,
            handler_path=entity.handler_path,
            resource_name=entity.resource_name,
            correlation_id=entity.correlation_id,
            payload=entity.payload,
            metadata=entity.metadata,
            error_type=entity.error_type,
            error_message=entity.error_message,
            status=entity.status.value,
            retry_count=entity.retry_count,
        )
        return self._to_entity(model)

    def get_by_id(self, id: uuid.UUID) -> FailedEventMessageEntity | None:
        model = FailedEventMessage.objects.filter(id=id).first()
        return self._to_entity(model) if model else None

    def mark_resolved(self, id: uuid.UUID) -> FailedEventMessageEntity:
        with transaction.atomic():
            model = self._locked_pending(id)
            model.status = FailedEventStatus.RESOLVED.value
            model.retry_count += 1
            model.save(update_fields=["status", "retry_count", "updated_at"])
            return self._to_entity(model)

    def mark_retry_failed(
        self, id: uuid.UUID, error_type: str, error_message: str
    ) -> FailedEventMessageEntity:
        with transaction.atomic():
            model = self._locked_pending(id)
            model.retry_count += 1
            model.error_type = error_type
            model.error_message = error_message
            model.save(
                update_fields=[
                    "retry_count",
                    "error_type",
                    "error_message",
                    "updated_at",
                ]
            )
            return self._to_entity(model)

    @staticmethod
    def _locked_pending(id: uuid.UUID) -> FailedEventMessage:
        """Fetches the row for a mutation, holding a row lock (where the
        backend supports `SELECT ... FOR UPDATE`) and restricted to rows
        still `PENDING` — a concurrent caller that already resolved or
        retried this row makes it disappear from this query rather than
        being silently overwritten."""
        model = (
            FailedEventMessage.objects.select_for_update()
            .filter(id=id, status=FailedEventStatus.PENDING.value)
            .first()
        )
        if model is None:
            raise FailedEventMessageNotFoundError(id)
        return model

    @staticmethod
    def _to_entity(model: FailedEventMessage) -> FailedEventMessageEntity:
        return FailedEventMessageEntity(
            id=model.id,
            channel_path=model.channel_path,
            handler_path=model.handler_path,
            resource_name=model.resource_name,
            correlation_id=model.correlation_id,
            payload=model.payload or {},
            metadata=model.metadata or {},
            error_type=model.error_type,
            error_message=model.error_message,
            status=FailedEventStatus(model.status),
            retry_count=model.retry_count,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
