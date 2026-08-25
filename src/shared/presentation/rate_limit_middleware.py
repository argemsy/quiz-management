from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from main.project_settings import settings
from src.shared.infrastructure.cache import check_and_increment
from src.shared.infrastructure.logging import LogDomain, get_logger

logger = get_logger(LogDomain.SHARED)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """General per-IP request bound, applied to every request before
    `AuthMiddleware` runs — rejects before paying for JWT decode or GraphQL
    execution. Identifies the client via `request.client.host` (the actual
    TCP peer address), never a client-suppliable header: this deployment has
    no reverse proxy in front of `uvicorn` (see `devops/docker-compose.yaml`)
    to set `X-Forwarded-For` trustworthily, so trusting that header would
    make the limit trivially bypassable. A separate, stricter bucket for the
    `login` mutation lives in `LoginService.login()` — this middleware can't
    tell mutations apart without parsing the GraphQL document, so it only
    enforces the general bound. See design.md - Decisions
    (mutation-idempotency-rate-limit).
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.client is None:
            return await call_next(request)

        allowed, retry_after = await check_and_increment(
            f"rate_limit:general:{request.client.host}",
            settings.RATE_LIMIT.general_limit,
            settings.RATE_LIMIT.general_window_seconds,
        )
        if not allowed:
            logger.info("rate_limit_exceeded", scope="general", ip=request.client.host)
            return JSONResponse(
                status_code=429,
                content={"code": "RATE_LIMITED"},
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
