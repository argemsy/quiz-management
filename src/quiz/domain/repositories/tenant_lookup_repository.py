import uuid
from abc import ABC, abstractmethod


class TenantLookupRepository(ABC):
    """Port `quiz` defines for the read-only tenant/tenant_user checks it
    needs — `quiz` does not own this data, so it never imports `tenant`'s
    Django models directly; only this port's implementation does."""

    @abstractmethod
    async def tenant_exists(self, tenant_id: uuid.UUID) -> bool:
        pass

    @abstractmethod
    async def tenant_user_exists(
        self, tenant_id: uuid.UUID, tenant_user_id: uuid.UUID
    ) -> bool:
        pass
