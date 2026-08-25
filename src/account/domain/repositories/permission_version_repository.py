import uuid
from abc import ABC, abstractmethod


class PermissionVersionRepository(ABC):
    """Two independent version counters, matching the two independent
    sources of permission in this system (see design.md - Decisions):
    a global one for `MyUser.is_superuser` (`IS_STAFF`), and one per
    `UserTenant` membership for `role` (`IS_ADMIN`/`IS_COLLABORATOR`).

    A missing key and version `0` are equivalent by convention: a session
    minted before any bump for its scope carries `0`, and a repository
    with no data for that scope also returns `0` — so a freshly-issued
    session compares equal without requiring a bump on issuance.
    """

    @abstractmethod
    async def get_user_version(self, user_id: uuid.UUID) -> int:
        pass

    @abstractmethod
    async def get_user_tenant_version(self, user_tenant_id: uuid.UUID) -> int:
        pass

    @abstractmethod
    async def bump_user_version(self, user_id: uuid.UUID) -> int:
        pass

    @abstractmethod
    async def bump_user_tenant_version(self, user_tenant_id: uuid.UUID) -> int:
        pass
