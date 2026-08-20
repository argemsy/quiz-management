from src.account.application.session_claims_service import SessionClaimsService
from src.account.domain.exceptions import InvalidSessionError
from src.account.domain.repositories.user_repository import UserRepository
from src.shared.domain.specification import FieldFilterSpecification
from src.shared.infrastructure.auth import (
    SessionClaims,
    TokenExpiredError,
    TokenInvalidError,
    TokenService,
)


class RefreshSessionService:
    """Per specs/account/auth-session/spec.md: a stale-but-identity-valid
    session can be refreshed without a password; an expired or tampered
    one is rejected outright, same as a first-time invalid login. This
    always re-derives fresh permissions (not just for the version that
    was stale) — cheaper to always be correct than to track which of the
    two independent version scopes actually triggered the refresh.
    """

    def __init__(
        self,
        user_repository: UserRepository,
        session_claims_service: SessionClaimsService,
        token_service: TokenService,
    ) -> None:
        self.user_repository = user_repository
        self.session_claims_service = session_claims_service
        self.token_service = token_service

    async def refresh(self, token: str) -> SessionClaims:
        try:
            old_claims = self.token_service.decode(token)
        except TokenExpiredError as exc:
            raise InvalidSessionError("token expired") from exc
        except TokenInvalidError as exc:
            raise InvalidSessionError("token invalid") from exc

        users = await self.user_repository.find(
            FieldFilterSpecification(id=old_claims.user_id)
        )
        if not users:
            raise InvalidSessionError("user no longer exists")

        return await self.session_claims_service.assemble(
            users[0], old_claims.active_tenant_id
        )
