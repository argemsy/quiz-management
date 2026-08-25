from redis.exceptions import RedisError

from src.shared.infrastructure.cache.redis_client import get_redis_client
from src.shared.infrastructure.logging import LogDomain, get_logger

logger = get_logger(LogDomain.SHARED)


async def check_and_increment(
    key: str, limit: int, window_seconds: int
) -> tuple[bool, int]:
    """Atomic fixed-window rate check via Redis `INCR`+`EXPIRE`. Checking the
    result of the increment itself — not a separate prior read — is what
    avoids a check-then-write race under concurrent requests sharing `key`:
    Redis executes commands one at a time, so `INCR` always returns a
    correct sequential count no matter how many requests arrive in
    parallel. Fails open (allowed=True) if Redis is unreachable, same
    precedent as `AuthMiddleware._is_stale` — see design.md - Decisions
    (mutation-idempotency-rate-limit).

    Returns `(allowed, retry_after_seconds)`.
    """
    client = get_redis_client()
    try:
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, window_seconds)
        if count > limit:
            ttl = await client.ttl(key)
            return False, max(ttl, 1)
        return True, 0
    except RedisError as exc:
        logger.warning("rate_limit_store_unreachable", key=key, error=str(exc))
        return True, 0
