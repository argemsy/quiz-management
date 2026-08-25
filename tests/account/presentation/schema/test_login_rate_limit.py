import uuid

import pytest
import pytest_asyncio
from asgiref.sync import sync_to_async
from httpx import ASGITransport, AsyncClient

from main.asgi import fastapp
from main.project_settings import settings
from src.account.infrastructure.persistence.django.models import MyUser
from src.shared.infrastructure.cache import RedisClientRegistry, create_redis_client
from tests.tools.graphql import read_graphql

pytestmark = pytest.mark.django_db(transaction=True)

LOGIN_MUTATION = read_graphql("tests/graphql/mutations/login.graphql")
TYPENAME_QUERY = read_graphql("tests/graphql/queries/typename.graphql")


@pytest.fixture(autouse=True)
def _reset_redis_registry():
    RedisClientRegistry.reset_for_tests()
    yield
    RedisClientRegistry.reset_for_tests()


@pytest_asyncio.fixture(autouse=True)
async def _isolate_rate_limit_keys():
    async def _clear():
        client = create_redis_client()
        async for key in client.scan_iter(match="rate_limit:*"):
            await client.delete(key)
        await client.aclose()

    await _clear()
    yield
    await _clear()


@pytest.fixture
def _low_login_limit(monkeypatch):
    monkeypatch.setattr(settings.RATE_LIMIT, "login_limit", 2)
    monkeypatch.setattr(settings.RATE_LIMIT, "login_window_seconds", 900)
    monkeypatch.setattr(settings.RATE_LIMIT, "general_limit", 1000)


async def _login(client, headers=None):
    return await client.post(
        "/api/graph/quizzes/",
        json={
            "query": LOGIN_MUTATION,
            "variables": {
                "email": "nobody@example.com",
                "password": "wrong",
                "tenantId": None,
            },
        },
        headers=headers
        or {
            "X-Correlation-ID": str(uuid.uuid4()),
            "X-Operation-ID": str(uuid.uuid4()),
        },
    )


async def _query(client):
    return await client.post(
        "/api/graph/quizzes/",
        json={"query": TYPENAME_QUERY},
    )


@pytest.mark.asyncio
async def test_login_attempts_beyond_the_login_limit_are_rejected(_low_login_limit):
    transport = ASGITransport(app=fastapp)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(2):
            resp = await _login(client)
            payload = resp.json()["data"]["account"]["login"]
            assert payload["__typename"] == "ValidationErrorResponse"

        blocked = await _login(client)

    blocked_payload = blocked.json()["data"]["account"]["login"]
    assert blocked_payload["__typename"] == "IntegrityErrorResponse"
    assert "Too many login attempts" in blocked_payload["message"]


@pytest.mark.asyncio
async def test_exhausted_login_limit_does_not_block_other_requests(_low_login_limit):
    await sync_to_async(MyUser.objects.create_user, thread_sensitive=True)(
        username="alice",
        email="alice@example.com",
        password="s3cret-pw",
        is_superuser=True,
    )

    transport = ASGITransport(app=fastapp)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(2):
            await _login(client)
        blocked = await _login(client)
        assert (
            blocked.json()["data"]["account"]["login"]["__typename"]
            == "IntegrityErrorResponse"
        )

        # Same IP, a query instead of `login` — only the general bucket
        # applies, and it's set high enough here not to interfere.
        other = await _query(client)

    assert other.status_code == 200
    assert other.json()["data"]["__typename"] == "Query"
