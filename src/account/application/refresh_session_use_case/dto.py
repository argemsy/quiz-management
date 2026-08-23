import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict

from src.shared.application.dto import CorrelationIdDTO


class RefreshSessionDTO(CorrelationIdDTO):
    model_config = ConfigDict(frozen=True)

    token: str


class RefreshSessionResultDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    token: str
    is_staff: bool
    active_tenant_id: Optional[uuid.UUID] = None
    role: Optional[str] = None
