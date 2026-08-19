from src.account.application.refresh_session_use_case.dto import (
    RefreshSessionDTO,
    RefreshSessionResultDTO,
)
from src.account.application.refresh_session_use_case.service import (
    RefreshSessionService,
)
from src.shared.infrastructure.auth import TokenService
from src.shared.infrastructure.logging import get_logger

logger = get_logger(__name__)


class RefreshSessionUseCase:
    def __init__(
        self,
        refresh_session_service: RefreshSessionService,
        token_service: TokenService,
    ) -> None:
        self.refresh_session_service = refresh_session_service
        self.token_service = token_service

    async def execute(self, dto: RefreshSessionDTO) -> RefreshSessionResultDTO:
        claims = await self.refresh_session_service.refresh(dto.token)
        token = self.token_service.encode(claims)

        logger.info("session_refreshed", user_id=str(claims.user_id))

        return RefreshSessionResultDTO(
            token=token,
            is_staff=claims.is_staff,
            active_tenant_id=claims.active_tenant_id,
            role=claims.role,
        )
