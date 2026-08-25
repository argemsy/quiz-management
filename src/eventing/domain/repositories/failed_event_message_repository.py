import uuid
from abc import ABC, abstractmethod

from src.eventing.domain.entities.failed_event_message_entity import (
    FailedEventMessageEntity,
)


class FailedEventMessageRepository(ABC):
    @abstractmethod
    def save(self, entity: FailedEventMessageEntity) -> FailedEventMessageEntity:
        pass

    @abstractmethod
    def get_by_id(self, id: uuid.UUID) -> FailedEventMessageEntity | None:
        pass

    @abstractmethod
    def mark_resolved(self, id: uuid.UUID) -> FailedEventMessageEntity:
        pass

    @abstractmethod
    def mark_retry_failed(
        self, id: uuid.UUID, error_type: str, error_message: str
    ) -> FailedEventMessageEntity:
        pass
