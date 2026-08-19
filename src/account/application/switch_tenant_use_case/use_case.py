from src.account.application.switch_tenant_use_case.dto import (
    SwitchTenantDTO,
    SwitchTenantResultDTO,
)
from src.account.application.switch_tenant_use_case.service import (
    SwitchTenantService,
)
from src.shared.infrastructure.auth import TokenService
from src.shared.infrastructure.logging import get_logger

logger = get_logger(__name__)


class SwitchTenantUseCase:
    def __init__(
        self,
        switch_tenant_service: SwitchTenantService,
        token_service: TokenService,
    ) -> None:
        self.switch_tenant_service = switch_tenant_service
        self.token_service = token_service

    async def execute(self, dto: SwitchTenantDTO) -> SwitchTenantResultDTO:
        claims = await self.switch_tenant_service.switch_tenant(
            dto.user_id, dto.tenant_id
        )
        token = self.token_service.encode(claims)

        logger.info(
            "tenant_switched",
            user_id=str(claims.user_id),
            active_tenant_id=str(claims.active_tenant_id),
        )

        return SwitchTenantResultDTO(
            token=token,
            active_tenant_id=claims.active_tenant_id,
            role=claims.role,
        )
