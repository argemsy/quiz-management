import contextlib

from redis.exceptions import RedisError

from src.shared.infrastructure.cache.redis_client import get_redis_client
from src.shared.infrastructure.logging import LogDomain, get_logger

logger = get_logger(LogDomain.SHARED)

_LOCK_TTL_SECONDS = 30


def _lock_key(operation_id: str) -> str:
    return f"idempotency_lock:{operation_id}"


async def try_acquire_fast_path_lock(operation_id: str) -> bool:
    """Best-effort Redis lock to short-circuit an obviously-concurrent
    duplicate mutation attempt without a Postgres round-trip. Fails open
    (returns True, i.e. "proceed") if Redis is unreachable — the actual
    duplicate-record guarantee is the Postgres unique constraint on
    `IdempotencyKey.operation_id`, not this lock; same fail-open precedent
    as `AuthMiddleware._is_stale`. Short TTL bounds how long a crashed
    worker can hold the lock without needing an explicit release.
    """
    client = get_redis_client()
    try:
        acquired = await client.set(
            _lock_key(operation_id), "1", nx=True, ex=_LOCK_TTL_SECONDS
        )
    except RedisError as exc:
        logger.warning(
            "idempotency_lock_store_unreachable",
            operation_id=operation_id,
            error=str(exc),
        )
        return True
    return bool(acquired)


async def release_fast_path_lock(operation_id: str) -> None:
    client = get_redis_client()
    with contextlib.suppress(RedisError):
        await client.delete(_lock_key(operation_id))
