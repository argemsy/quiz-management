import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict


class SessionClaims(BaseModel):
    """What a session token carries. Deliberately generic (no account-app
    enums) — this lives in `shared` so both the auth middleware and any
    future issuer can depend on it without a cross-app import. `role` is a
    plain string; the account app is responsible for giving it meaning.

    One active tenant per session (see design.md - Decisions: Slack-style,
    not a multi-tenant claims array). `active_tenant_id`/`user_tenant_id`/
    `role`/`user_tenant_version` are all None together for a staff-only
    session with no tenant context.
    """

    model_config = ConfigDict(frozen=True)

    user_id: uuid.UUID
    is_staff: bool
    active_tenant_id: Optional[uuid.UUID] = None
    user_tenant_id: Optional[uuid.UUID] = None
    role: Optional[str] = None
    user_version: int = 0
    user_tenant_version: int = 0
