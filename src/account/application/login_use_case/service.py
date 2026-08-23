import uuid

from src.account.application.session_claims_service import SessionClaimsService
from src.account.domain.exceptions import InvalidCredentialsError, TenantRequiredError
from src.account.domain.repositories.user_repository import UserRepository
from src.shared.infrastructure.auth import SessionClaims


class LoginService:
    def __init__(
        self,
        user_repository: UserRepository,
        session_claims_service: SessionClaimsService,
    ) -> None:
        self.user_repository = user_repository
        self.session_claims_service = session_claims_service

    async def login(
        self, email: str, password: str, tenant_id: uuid.UUID | None
    ) -> SessionClaims:

        user = await self.user_repository.authenticate(email, password)

        if user is None:
            raise InvalidCredentialsError()

        if tenant_id is None and not user.is_superuser:
            raise TenantRequiredError()

        return await self.session_claims_service.assemble(user, tenant_id)
