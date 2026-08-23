import uuid

import strawberry

from main.project_settings import settings
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
from src.shared.infrastructure.cache import check_and_increment, get_redis_client
from src.shared.presentation.decorators import handle_mutations_exceptions
from src.shared.presentation.schema.context import Info
from src.shared.presentation.schema.permissions import IsAuthenticated
from src.shared.presentation.schema.responses import IntegrityErrorResponse


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
        correlation_id = info.context.correlation_id
        request = info.context.request
        if request is not None and request.client is not None:
            # Stricter, separate bucket from `RateLimitMiddleware`'s general
            # one — credential brute-forcing needs a much tighter bound than
            # ordinary traffic, and the middleware can't single out `login`
            # without parsing the GraphQL document itself. See design.md -
            # Decisions (mutation-idempotency-rate-limit).
            allowed, retry_after = await check_and_increment(
                f"rate_limit:login:{request.client.host}",
                settings.RATE_LIMIT.login_limit,
                settings.RATE_LIMIT.login_window_seconds,
            )
            if not allowed:
                return IntegrityErrorResponse(
                    correlation_id=correlation_id,
                    message=(
                        "Too many login attempts from this address; retry "
                        f"in {retry_after}s."
                    ),
                )

        dto = LoginDTO.model_validate(
            {**strawberry.asdict(input), "correlation_id": correlation_id}
        )
        use_case = LoginUseCase(
            LoginService(UserRepositoryImpl(), _session_claims_service()),
            get_token_service(),
        )
        result = await use_case.execute(dto)

        return LoginPayload(
            correlation_id=correlation_id,
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
        correlation_id = info.context.correlation_id
        dto = SwitchTenantDTO(
            user_id=uuid.UUID(info.context.user_session.user_id),
            tenant_id=input.tenant_id,
            correlation_id=correlation_id,
        )
        use_case = SwitchTenantUseCase(
            SwitchTenantService(UserRepositoryImpl(), _session_claims_service()),
            get_token_service(),
        )
        result = await use_case.execute(dto)

        return SwitchTenantPayload(
            correlation_id=correlation_id,
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
        correlation_id = info.context.correlation_id
        dto = RefreshSessionDTO(token=input.token, correlation_id=correlation_id)
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
            correlation_id=correlation_id,
            token=result.token,
            is_staff=result.is_staff,
            active_tenant_id=(
                str(result.active_tenant_id) if result.active_tenant_id else None
            ),
            role=result.role,
        )
