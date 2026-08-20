import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict


class RefreshSessionDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    token: str


class RefreshSessionResultDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    token: str
    is_staff: bool
    active_tenant_id: Optional[uuid.UUID] = None
    role: Optional[str] = None
