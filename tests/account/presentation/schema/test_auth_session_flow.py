import uuid

import pytest
from asgiref.sync import sync_to_async
from django.contrib import admin
from django.db import connection, reset_queries
from django.test import RequestFactory
from httpx import ASGITransport, AsyncClient

from main.asgi import fastapp
from src.account.infrastructure.persistence.django.models import (
    MyUser,
    TenantModel,
    UserTenantModel,
)
from src.account.presentation.admin.user_tenant import UserTenantAdmin
from src.account.shared.account_enums import TenantTypeEnum, UserTenantRoleEnum
from src.shared.infrastructure.cache import RedisClientRegistry

pytestmark = pytest.mark.django_db(transaction=True)

LOGIN_MUTATION = """
mutation Login($email: String!, $password: String!, $tenantId: ID) {
  account {
    login(input: {email: $email, password: $password, tenant_id: $tenantId}) {
      __typename
      ... on LoginSuccess { token is_staff active_tenant_id role }
      ... on ValidationErrorResponse { message }
    }
  }
}
"""

REFRESH_MUTATION = """
mutation Refresh($token: String!) {
  account {
    refresh_session(input: {token: $token}) {
      __typename
      ... on RefreshSessionSuccess { token is_staff active_tenant_id role }
      ... on ValidationErrorResponse { message }
    }
  }
}
"""

SWITCH_TENANT_MUTATION = """
mutation SwitchTenant($tenantId: ID!) {
  account {
    switch_tenant(input: {tenant_id: $tenantId}) {
      __typename
      ... on SwitchTenantSuccess { token active_tenant_id role }
      ... on ValidationErrorResponse { message }
    }
  }
}
"""

TYPENAME_QUERY = "{ __typename }"


@pytest.fixture(autouse=True)
def _reset_redis_registry():
    """`redis.asyncio` connections are bound to the event loop they were
    created on; pytest-asyncio opens a fresh loop per test, same reason
    `tests/fixtures/account_fixtures.py::redis_client` resets this."""
    RedisClientRegistry.reset_for_tests()
    yield
    RedisClientRegistry.reset_for_tests()


def _headers(operation_id: str | None = None, token: str | None = None) -> dict:
    headers = {"X-Operation-ID": operation_id or str(uuid.uuid4())}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


async def _post_graphql(client, query, variables=None, **kwargs):
    return await client.post(
        "/api/graph/quizzes/",
        json={"query": query, "variables": variables or {}},
        headers=_headers(**kwargs),
    )


def _create_membership(
    *, role: str, is_superuser: bool = False
) -> tuple[TenantModel, MyUser, UserTenantModel]:
    tenant = TenantModel.objects.create(
        tenant_type=TenantTypeEnum.COMPANY.value,
        name="Acme Inc",
        slug="acme-inc",
    )
    user = MyUser.objects.create_user(
        username="alice",
        email="alice@example.com",
        password="s3cret-pw",
        is_superuser=is_superuser,
    )
    user_tenant = UserTenantModel.objects.create(
        user=user, tenant=tenant, role=role, is_active=True
    )
    return tenant, user, user_tenant


@pytest.mark.asyncio
async def test_login_then_verified_request_makes_no_permission_db_query():
    tenant, user, _ = await sync_to_async(_create_membership, thread_sensitive=True)(
        role=UserTenantRoleEnum.COLLABORATOR.value
    )

    transport = ASGITransport(app=fastapp)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_resp = await _post_graphql(
            client,
            LOGIN_MUTATION,
            {"email": user.email, "password": "s3cret-pw", "tenantId": str(tenant.id)},
        )
        assert login_resp.status_code == 200
        login_payload = login_resp.json()["data"]["account"]["login"]
        assert login_payload["__typename"] == "LoginSuccess"
        token = login_payload["token"]

        reset_queries()
        second_resp = await _post_graphql(client, TYPENAME_QUERY, token=token)

        assert second_resp.status_code == 200
        assert second_resp.json()["data"]["__typename"] == "Query"
        assert connection.queries == []


@pytest.mark.asyncio
async def test_role_change_stales_session_then_refresh_recovers_it():
    tenant, user, user_tenant = await sync_to_async(
        _create_membership, thread_sensitive=True
    )(role=UserTenantRoleEnum.COLLABORATOR.value)

    transport = ASGITransport(app=fastapp)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_resp = await _post_graphql(
            client,
            LOGIN_MUTATION,
            {"email": user.email, "password": "s3cret-pw", "tenantId": str(tenant.id)},
        )
        old_token = login_resp.json()["data"]["account"]["login"]["token"]

        # Admin changes the membership's role — publishes ENTITY_CHANGED,
        # `handle_entity_changed_for_permissions` bumps the Redis version
        # synchronously (see tasks.md 6.1b) before `save_model` returns.
        def _bump_role_via_admin():
            admin_instance = UserTenantAdmin(UserTenantModel, admin.site)
            admin_instance.message_user = lambda *a, **k: None
            admin_request = RequestFactory().post("/admin/")
            admin_request.user = user
            user_tenant.role = UserTenantRoleEnum.ADMIN.value
            admin_instance.save_model(
                admin_request, user_tenant, form=None, change=True
            )

        await sync_to_async(_bump_role_via_admin, thread_sensitive=True)()

        stale_resp = await _post_graphql(client, TYPENAME_QUERY, token=old_token)
        assert stale_resp.status_code == 401
        assert stale_resp.json() == {"code": "SESSION_STALE"}

        refresh_resp = await _post_graphql(
            client, REFRESH_MUTATION, {"token": old_token}
        )
        refresh_payload = refresh_resp.json()["data"]["account"]["refresh_session"]
        assert refresh_payload["__typename"] == "RefreshSessionSuccess"
        assert refresh_payload["role"] == UserTenantRoleEnum.ADMIN.value
        new_token = refresh_payload["token"]

        retry_resp = await _post_graphql(client, TYPENAME_QUERY, token=new_token)
        assert retry_resp.status_code == 200


@pytest.mark.asyncio
async def test_redis_unreachable_fails_open_and_logs_a_warning(monkeypatch, caplog):
    import redis.asyncio as redis_asyncio

    tenant, user, _ = await sync_to_async(_create_membership, thread_sensitive=True)(
        role=UserTenantRoleEnum.COLLABORATOR.value
    )

    unreachable_client = redis_asyncio.from_url(
        "redis://localhost:1/0",
        socket_timeout=0.2,
        socket_connect_timeout=0.2,
        decode_responses=True,
    )
    monkeypatch.setattr(
        "src.shared.presentation.auth_middleware.get_redis_client",
        lambda: unreachable_client,
    )

    transport = ASGITransport(app=fastapp)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_resp = await _post_graphql(
            client,
            LOGIN_MUTATION,
            {"email": user.email, "password": "s3cret-pw", "tenantId": str(tenant.id)},
        )
        token = login_resp.json()["data"]["account"]["login"]["token"]

        with caplog.at_level("WARNING"):
            resp = await _post_graphql(client, TYPENAME_QUERY, token=token)

    assert resp.status_code == 200
    assert "permission_version_store_unreachable" in caplog.text
    await unreachable_client.aclose()


@pytest.mark.asyncio
async def test_staff_login_then_switch_tenant_succeeds():
    tenant, user, _ = await sync_to_async(_create_membership, thread_sensitive=True)(
        role=UserTenantRoleEnum.COLLABORATOR.value, is_superuser=True
    )

    transport = ASGITransport(app=fastapp)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_resp = await _post_graphql(
            client,
            LOGIN_MUTATION,
            {"email": user.email, "password": "s3cret-pw", "tenantId": None},
        )
        login_payload = login_resp.json()["data"]["account"]["login"]
        assert login_payload["__typename"] == "LoginSuccess"
        assert login_payload["is_staff"] is True
        assert login_payload["active_tenant_id"] is None
        token = login_payload["token"]

        switch_resp = await _post_graphql(
            client, SWITCH_TENANT_MUTATION, {"tenantId": str(tenant.id)}, token=token
        )
        switch_payload = switch_resp.json()["data"]["account"]["switch_tenant"]
        assert switch_payload["__typename"] == "SwitchTenantSuccess"
        assert switch_payload["active_tenant_id"] == str(tenant.id)
        assert switch_payload["role"] == UserTenantRoleEnum.COLLABORATOR.value
