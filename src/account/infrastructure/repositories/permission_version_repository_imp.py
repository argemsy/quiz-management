import uuid

from redis.asyncio import Redis

from src.account.domain.repositories.permission_version_repository import (
    PermissionVersionRepository,
)


def _user_key(user_id: uuid.UUID) -> str:
    return f"perms_version:user:{user_id}"


def _user_tenant_key(user_tenant_id: uuid.UUID) -> str:
    return f"perms_version:user_tenant:{user_tenant_id}"


class PermissionVersionRepositoryImpl(PermissionVersionRepository):
    """Native async implementation (not `@async_database()` — that decorator
    bridges Django's sync ORM into async use cases; `redis.asyncio` is
    already async, nothing to bridge). Callers on the request hot path
    (the auth middleware) are expected to catch connection/timeout errors
    from these calls themselves and apply the fail-open policy from
    design.md - Decisions; this repository does not swallow them."""

    def __init__(self, client: Redis) -> None:
        self.client = client

    async def get_user_version(self, user_id: uuid.UUID) -> int:
        value = await self.client.get(_user_key(user_id))
        return int(value) if value is not None else 0

    async def get_user_tenant_version(self, user_tenant_id: uuid.UUID) -> int:
        value = await self.client.get(_user_tenant_key(user_tenant_id))
        return int(value) if value is not None else 0

    async def bump_user_version(self, user_id: uuid.UUID) -> int:
        return await self.client.incr(_user_key(user_id))

    async def bump_user_tenant_version(self, user_tenant_id: uuid.UUID) -> int:
        return await self.client.incr(_user_tenant_key(user_tenant_id))
