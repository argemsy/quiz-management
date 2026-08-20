import uuid

import strawberry

from src.account.application.login_use_case.dto import LoginDTO
from src.account.application.login_use_case.service import LoginService
from src.account.application.login_use_case.use_case import LoginUseCase
from src.account.application.refresh_session_use_case.dto import RefreshSessionDTO
from src.account.application.refresh_session_use_case.service import (
    RefreshSessionService,
)
from src.account.application.refresh_session_use_case.use_case import (
    RefreshSessionUseCase,
)
from src.account.application.session_claims_service import SessionClaimsService
from src.account.application.switch_tenant_use_case.dto import SwitchTenantDTO
from src.account.application.switch_tenant_use_case.service import (
    SwitchTenantService,
)
from src.account.application.switch_tenant_use_case.use_case import (
    SwitchTenantUseCase,
)
from src.account.infrastructure.repositories import (
    PermissionVersionRepositoryImpl,
    UserRepositoryImpl,
    UserTenantRepositoryImpl,
)
from src.account.presentation.schema.inputs.login_input import LoginInput
from src.account.presentation.schema.inputs.refresh_session_input import (
    RefreshSessionInput,
)
from src.account.presentation.schema.inputs.switch_tenant_input import (
    SwitchTenantInput,
)
from src.account.presentation.schema.responses.login_response import (
    LoginPayload,
    LoginResponse,
)
from src.account.presentation.schema.responses.refresh_session_response import (
    RefreshSessionPayload,
    RefreshSessionResponse,
)
from src.account.presentation.schema.responses.switch_tenant_response import (
    SwitchTenantPayload,
    SwitchTenantResponse,
)
from src.shared.infrastructure.auth import get_token_service
from src.shared.infrastructure.cache import get_redis_client
from src.shared.presentation.decorators import handle_mutations_exceptions
from src.shared.presentation.schema.context import Info
from src.shared.presentation.schema.permissions import IsAuthenticated


def _session_claims_service() -> SessionClaimsService:
    return SessionClaimsService(
        user_tenant_repository=UserTenantRepositoryImpl(),
        permission_version_repository=PermissionVersionRepositoryImpl(
            get_redis_client()
        ),
    )


@strawberry.type
class AccountMutation:

    @strawberry.mutation
    @handle_mutations_exceptions
    async def login(self, info: Info, input: LoginInput) -> LoginResponse:
        operation_id = info.context.operation_id
        dto = LoginDTO.model_validate(strawberry.asdict(input))
        use_case = LoginUseCase(
            LoginService(UserRepositoryImpl(), _session_claims_service()),
            get_token_service(),
        )
        result = await use_case.execute(dto)

        return LoginPayload(
            operation_id=operation_id,
            token=result.token,
            is_staff=result.is_staff,
            active_tenant_id=(
                str(result.active_tenant_id) if result.active_tenant_id else None
            ),
            role=result.role,
        )

    @strawberry.mutation(permission_classes=[IsAuthenticated])
    @handle_mutations_exceptions
    async def switch_tenant(
        self, info: Info, input: SwitchTenantInput
    ) -> SwitchTenantResponse:
        operation_id = info.context.operation_id
        dto = SwitchTenantDTO(
            user_id=uuid.UUID(info.context.user_session.user_id),
            tenant_id=input.tenant_id,
        )
        use_case = SwitchTenantUseCase(
            SwitchTenantService(UserRepositoryImpl(), _session_claims_service()),
            get_token_service(),
        )
        result = await use_case.execute(dto)

        return SwitchTenantPayload(
            operation_id=operation_id,
            token=result.token,
            active_tenant_id=(
                str(result.active_tenant_id) if result.active_tenant_id else None
            ),
            role=result.role,
        )

    @strawberry.mutation
    @handle_mutations_exceptions
    async def refresh_session(
        self, info: Info, input: RefreshSessionInput
    ) -> RefreshSessionResponse:
        operation_id = info.context.operation_id
        dto = RefreshSessionDTO(token=input.token)
        use_case = RefreshSessionUseCase(
            RefreshSessionService(
                UserRepositoryImpl(),
                _session_claims_service(),
                get_token_service(),
            ),
            get_token_service(),
        )
        result = await use_case.execute(dto)

        return RefreshSessionPayload(
            operation_id=operation_id,
            token=result.token,
            is_staff=result.is_staff,
            active_tenant_id=(
                str(result.active_tenant_id) if result.active_tenant_id else None
            ),
            role=result.role,
        )
