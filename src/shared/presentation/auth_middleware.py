from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.account.infrastructure.repositories.permission_version_repository_imp import (
    PermissionVersionRepositoryImpl,
)
from src.shared.infrastructure.auth import (
    SessionClaims,
    TokenExpiredError,
    TokenInvalidError,
    get_token_service,
)
from src.shared.infrastructure.cache import get_redis_client
from src.shared.infrastructure.logging import LogDomain, get_logger
from src.shared.presentation.schema.permissions import SessionPermissionEnum
from src.shared.presentation.schema.types import UserSession

logger = get_logger(LogDomain.SHARED)

_ADMIN_ROLES = {"ADMIN", "DIRECTOR"}
_COLLABORATOR_ROLES = {"COLLABORATOR"}


class AuthMiddleware(BaseHTTPMiddleware):
    """Verifies and populates `request.state.user_session`; never rejects
    for "not authenticated" (see design.md - Decisions). The only reject
    path is a stale permission-version on an otherwise-valid token, which
    short-circuits as a raw 401 before GraphQL executes — distinct from
    the typed `AuthenticationError` GraphQL responses `permissions.py`
    still produces for "you don't have this permission".
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request.state.user_session = None

        authorization = request.headers.get("Authorization")
        if not authorization:
            return await call_next(request)

        scheme, _, token = authorization.partition(" ")
        if scheme != "Bearer" or not token:
            return await call_next(request)

        try:
            claims = get_token_service().decode(token)
        except (TokenExpiredError, TokenInvalidError):
            return await call_next(request)

        if await self._is_stale(claims):
            return JSONResponse(status_code=401, content={"code": "SESSION_STALE"})

        request.state.user_session = _build_user_session(claims)
        return await call_next(request)

    async def _is_stale(self, claims: SessionClaims) -> bool:
        repo = PermissionVersionRepositoryImpl(get_redis_client())

        try:
            current_user_version = await repo.get_user_version(claims.user_id)
        except RedisError as exc:
            logger.warning(
                "permission_version_store_unreachable",
                scope="user",
                user_id=str(claims.user_id),
                error=str(exc),
            )
            return False
        if current_user_version != claims.user_version:
            return True

        if claims.user_tenant_id is None:
            return False

        try:
            current_user_tenant_version = await repo.get_user_tenant_version(
                claims.user_tenant_id
            )
        except RedisError as exc:
            logger.warning(
                "permission_version_store_unreachable",
                scope="user_tenant",
                user_tenant_id=str(claims.user_tenant_id),
                error=str(exc),
            )
            return False

        return current_user_tenant_version != claims.user_tenant_version


def _build_user_session(claims: SessionClaims) -> UserSession:
    permissions = [SessionPermissionEnum.IS_AUTHENTICATED.value]
    if claims.is_staff:
        permissions.append(SessionPermissionEnum.IS_STAFF.value)
    if claims.role in _ADMIN_ROLES:
        permissions.append(SessionPermissionEnum.IS_ADMIN.value)
    elif claims.role in _COLLABORATOR_ROLES:
        permissions.append(SessionPermissionEnum.IS_COLLABORATOR.value)

    return UserSession(
        session_type="jwt",
        session_key=str(claims.user_id),
        session_data={"user_id": str(claims.user_id)},
        session_permissions=permissions,
        user_id=str(claims.user_id),
        active_tenant_id=(
            str(claims.active_tenant_id) if claims.active_tenant_id else None
        ),
        user_tenant_id=(str(claims.user_tenant_id) if claims.user_tenant_id else None),
        role=claims.role,
        user_version=claims.user_version,
        user_tenant_version=claims.user_tenant_version,
    )
