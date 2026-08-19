import uuid

import pytest

from src.account.domain.entities.user_entity import UserEntity
from src.account.domain.entities.user_tenant_entity import UserTenantEntity
from src.account.domain.repositories.permission_version_repository import (
    PermissionVersionRepository,
)
from src.account.domain.repositories.user_repository import UserRepository
from src.account.domain.repositories.user_tenant_repository import (
    UserTenantRepository,
)
from src.shared.domain.specification import (
    AndSpecification,
    FieldFilterSpecification,
    NotSpecification,
    OrSpecification,
    Specification,
)
from src.shared.infrastructure.cache import RedisClientRegistry, get_redis_client


def _matches(entity, spec: Specification) -> bool:
    """Minimal in-memory Specification evaluator for fakes — mirrors
    `to_django_q`'s recursion, but checks plain attribute equality against
    an entity instead of building a Django `Q`."""
    if isinstance(spec, FieldFilterSpecification):
        return all(getattr(entity, key) == value for key, value in spec.filters.items())
    if isinstance(spec, AndSpecification):
        return _matches(entity, spec.left) and _matches(entity, spec.right)
    if isinstance(spec, OrSpecification):
        return _matches(entity, spec.left) or _matches(entity, spec.right)
    if isinstance(spec, NotSpecification):
        return not _matches(entity, spec.spec)
    raise TypeError(f"Unsupported specification type: {type(spec)!r}")


class FakeUserRepository(UserRepository):
    """In-memory stand-in for `UserRepositoryImpl` — used to unit test
    login/switch-tenant/refresh orchestration without a database."""

    def __init__(self) -> None:
        self._users: dict[uuid.UUID, UserEntity] = {}
        self._passwords: dict[str, str] = {}

    def add_user(self, user: UserEntity, password: str) -> None:
        self._users[user.id] = user
        self._passwords[user.email] = password

    async def authenticate(self, email: str, password: str) -> UserEntity | None:
        if self._passwords.get(email) != password:
            return None
        return next((u for u in self._users.values() if u.email == email), None)

    async def find(self, spec: Specification) -> list[UserEntity]:
        return [u for u in self._users.values() if _matches(u, spec)]


class FakeUserTenantRepository(UserTenantRepository):
    def __init__(self) -> None:
        self._memberships: dict[uuid.UUID, UserTenantEntity] = {}

    def add_membership(self, membership: UserTenantEntity) -> None:
        self._memberships[membership.id] = membership

    async def find(self, spec: Specification) -> list[UserTenantEntity]:
        return [m for m in self._memberships.values() if _matches(m, spec)]


class FakePermissionVersionRepository(PermissionVersionRepository):
    def __init__(self) -> None:
        self._user_versions: dict[uuid.UUID, int] = {}
        self._user_tenant_versions: dict[uuid.UUID, int] = {}

    async def get_user_version(self, user_id: uuid.UUID) -> int:
        return self._user_versions.get(user_id, 0)

    async def get_user_tenant_version(self, user_tenant_id: uuid.UUID) -> int:
        return self._user_tenant_versions.get(user_tenant_id, 0)

    async def bump_user_version(self, user_id: uuid.UUID) -> int:
        self._user_versions[user_id] = self._user_versions.get(user_id, 0) + 1
        return self._user_versions[user_id]

    async def bump_user_tenant_version(self, user_tenant_id: uuid.UUID) -> int:
        self._user_tenant_versions[user_tenant_id] = (
            self._user_tenant_versions.get(user_tenant_id, 0) + 1
        )
        return self._user_tenant_versions[user_tenant_id]


@pytest.fixture
def fake_user_repository() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def fake_user_tenant_repository() -> FakeUserTenantRepository:
    return FakeUserTenantRepository()


@pytest.fixture
def fake_permission_version_repository() -> FakePermissionVersionRepository:
    return FakePermissionVersionRepository()


@pytest.fixture
def redis_client():
    """A fresh Redis client per test. `RedisClientRegistry` is a singleton
    (see src/shared/infrastructure/cache/redis_client.py) so that a single
    connection is reused across a running process — but pytest-asyncio
    opens a new event loop per test function, and `redis.asyncio`
    connections are bound to the loop they were created on. Reusing the
    cached client across tests raises "Event loop is closed" on the second
    test to touch it, so this resets the registry around each test,
    mirroring `EventBusRegistry.reset_for_tests()`.
    """
    RedisClientRegistry.reset_for_tests()
    client = get_redis_client()
    yield client
    RedisClientRegistry.reset_for_tests()
