import uuid

from src.shared.domain.exceptions import NotFoundError


class FailedEventMessageNotFoundError(NotFoundError):
    def __init__(self, id: uuid.UUID) -> None:
        super().__init__(f"FailedEventMessage {id} not found")
        self.id = id
