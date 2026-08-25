import threading

import redis.asyncio as redis

from main.project_settings import settings


def create_redis_client() -> redis.Redis:
    """Builds a new, unshared client. `redis.asyncio`'s connection pool
    binds to whichever event loop first runs a command through it — reused
    across independent `asyncio.run()` calls (e.g. from sync Django admin
    code, once per request in the same long-lived process), a shared
    client raises "Event loop is closed" on the second call, since the
    first call's loop is already gone by then. A caller that only wraps
    a single `asyncio.run()` (build → use → `aclose()`, all inside that
    one coroutine) should use this, not `get_redis_client()`'s singleton.
    """
    return redis.from_url(
        settings.REDIS.url.get_secret_value(),
        socket_timeout=settings.REDIS.socket_timeout_seconds,
        socket_connect_timeout=settings.REDIS.socket_timeout_seconds,
        decode_responses=True,
    )


class RedisClientRegistry:
    """Thread-safe lazy holder for the single, process-wide async Redis
    client, mirroring `EventBusRegistry`'s singleton style. Only safe for
    callers backed by one long-lived event loop (the FastAPI service's
    auth middleware) — a sync caller driving its own `asyncio.run()` per
    call should use `create_redis_client()` instead (see its docstring).
    """

    _instance: redis.Redis | None = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> redis.Redis:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = create_redis_client()
        return cls._instance

    @classmethod
    def reset_for_tests(cls) -> None:
        """Only for use in test fixtures."""
        cls._instance = None


def get_redis_client() -> redis.Redis:
    return RedisClientRegistry.get_instance()
