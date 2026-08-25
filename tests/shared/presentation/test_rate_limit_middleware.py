import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from main.asgi import fastapp
from main.project_settings import settings
from src.shared.infrastructure.cache import RedisClientRegistry, create_redis_client

pytestmark = pytest.mark.django_db(transaction=True)

TYPENAME_QUERY = "{ __typename }"


@pytest.fixture(autouse=True)
def _reset_redis_registry():
    RedisClientRegistry.reset_for_tests()
    yield
    RedisClientRegistry.reset_for_tests()


@pytest.fixture
def _low_general_limit(monkeypatch):
    monkeypatch.setattr(settings.RATE_LIMIT, "general_limit", 3)
    monkeypatch.setattr(settings.RATE_LIMIT, "general_window_seconds", 60)
    yield


async def _query(client, headers=None):
    return await client.post(
        "/api/graph/quizzes/",
        json={"query": TYPENAME_QUERY},
        headers=headers or {},
    )


@pytest_asyncio.fixture(autouse=True)
async def _clear_rate_limit_keys():
    async def _clear():
        # `create_redis_client()`, not the shared singleton: this fixture's
        # own connection must stay confined to a single coroutine/event
        # loop (see `create_redis_client`'s docstring) rather than reuse a
        # client another test bound to a now-closed loop.
        client = create_redis_client()
        async for key in client.scan_iter(match="rate_limit:general:*"):
            await client.delete(key)
        await client.aclose()

    await _clear()
    yield
    await _clear()


@pytest.mark.asyncio
async def test_requests_within_the_limit_pass_through(_low_general_limit):
    transport = ASGITransport(app=fastapp)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(3):
            resp = await _query(client)
            assert resp.status_code == 200


@pytest.mark.asyncio
async def test_request_over_the_limit_is_rejected_before_graphql_executes(
    _low_general_limit,
):
    transport = ASGITransport(app=fastapp)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(3):
            resp = await _query(client)
            assert resp.status_code == 200

        blocked = await _query(client)

    assert blocked.status_code == 429
    assert blocked.json() == {"code": "RATE_LIMITED"}
    assert "Retry-After" in blocked.headers


@pytest.mark.asyncio
async def test_concurrent_burst_never_admits_more_than_the_limit(_low_general_limit):
    transport = ASGITransport(app=fastapp)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        responses = await asyncio.gather(*(_query(client) for _ in range(10)))

    statuses = [r.status_code for r in responses]
    assert statuses.count(200) == 3
    assert statuses.count(429) == 7
