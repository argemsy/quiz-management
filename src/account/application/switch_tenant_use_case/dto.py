import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict

from src.shared.application.dto import CorrelationIdDTO


class SwitchTenantDTO(CorrelationIdDTO):
    """`user_id` is deliberately not client-supplied input — the mutation
    resolver fills it in from the authenticated session
    (`info.context.user_session`), never from a GraphQL argument, so a
    caller can't switch a session that isn't theirs."""

    model_config = ConfigDict(frozen=True)

    user_id: uuid.UUID
    tenant_id: uuid.UUID


class SwitchTenantResultDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    token: str
    active_tenant_id: Optional[uuid.UUID] = None
    role: Optional[str] = None
