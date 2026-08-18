import uuid

from src.quiz.domain.exceptions import TenantNotFoundError, TenantUserNotFoundError
from src.quiz.domain.repositories.tenant_lookup_repository import TenantLookupRepository


class TenantValidationService:
    def __init__(self, repository: TenantLookupRepository) -> None:
        self.repository = repository

    async def ensure_tenant_and_membership(
        self, tenant_id: uuid.UUID, tenant_user_id: uuid.UUID
    ) -> None:
        if not await self.repository.tenant_exists(tenant_id):
            raise TenantNotFoundError(tenant_id)

        if not await self.repository.tenant_user_exists(tenant_id, tenant_user_id):
            raise TenantUserNotFoundError(tenant_id, tenant_user_id)
