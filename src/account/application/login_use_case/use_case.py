from src.account.application.login_use_case.dto import LoginDTO, LoginResultDTO
from src.account.application.login_use_case.service import LoginService
from src.shared.infrastructure.auth import TokenService
from src.shared.infrastructure.logging import get_logger

logger = get_logger(__name__)


class LoginUseCase:
    def __init__(
        self, login_service: LoginService, token_service: TokenService
    ) -> None:
        self.login_service = login_service
        self.token_service = token_service

    async def execute(self, dto: LoginDTO) -> LoginResultDTO:
        claims = await self.login_service.login(dto.email, dto.password, dto.tenant_id)
        token = self.token_service.encode(claims)

        logger.info(
            "user_logged_in",
            user_id=str(claims.user_id),
            is_staff=claims.is_staff,
            active_tenant_id=(
                str(claims.active_tenant_id) if claims.active_tenant_id else None
            ),
        )

        return LoginResultDTO(
            token=token,
            is_staff=claims.is_staff,
            active_tenant_id=claims.active_tenant_id,
            role=claims.role,
        )
