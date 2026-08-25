from src.eventing.application.persist_failed_event_use_case.dto import (
    PersistFailedEventDTO,
)
from src.eventing.domain.entities.failed_event_message_entity import (
    FailedEventMessageEntity,
)
from src.eventing.domain.repositories.failed_event_message_repository import (
    FailedEventMessageRepository,
)


class PersistFailedEventUseCase:
    def __init__(self, repository: FailedEventMessageRepository) -> None:
        self.repository = repository

    def execute(self, dto: PersistFailedEventDTO) -> FailedEventMessageEntity:
        entity = FailedEventMessageEntity.create(
            channel_path=dto.channel_path,
            handler_path=dto.handler_path,
            resource_name=dto.resource_name,
            correlation_id=dto.correlation_id,
            payload=dto.payload,
            metadata=dto.metadata,
            error_type=dto.error_type,
            error_message=dto.error_message,
        )
        return self.repository.save(entity)
