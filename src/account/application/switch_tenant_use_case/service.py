import uuid

from src.account.application.session_claims_service import SessionClaimsService
from src.account.domain.exceptions import InvalidSessionError
from src.account.domain.repositories.user_repository import UserRepository
from src.shared.domain.specification import FieldFilterSpecification
from src.shared.infrastructure.auth import SessionClaims


class SwitchTenantService:
    """No password required — the caller is already authenticated (see
    design.md - Decisions); this only re-verifies that an active
    membership exists for the requested tenant."""

    def __init__(
        self,
        user_repository: UserRepository,
        session_claims_service: SessionClaimsService,
    ) -> None:
        self.user_repository = user_repository
        self.session_claims_service = session_claims_service

    async def switch_tenant(
        self, user_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> SessionClaims:
        users = await self.user_repository.find(FieldFilterSpecification(id=user_id))
        if not users:
            raise InvalidSessionError("user no longer exists")

        return await self.session_claims_service.assemble(users[0], tenant_id)
