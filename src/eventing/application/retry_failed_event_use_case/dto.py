import uuid

from pydantic import BaseModel, ConfigDict


class RetryFailedEventDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    failed_event_id: uuid.UUID
