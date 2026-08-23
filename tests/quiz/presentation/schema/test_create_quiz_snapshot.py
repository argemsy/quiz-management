import uuid

import pytest
from asgiref.sync import sync_to_async
from httpx import ASGITransport, AsyncClient

from main.asgi import fastapp
from src.account.infrastructure.persistence.django.models import (
    MyUser,
    TenantModel,
    UserTenantModel,
)
from src.account.shared.account_enums import TenantTypeEnum, UserTenantRoleEnum
from src.shared.infrastructure.auth import SessionClaims, get_token_service
from tests.tools.graphql import read_graphql

pytestmark = pytest.mark.django_db(transaction=True)

CREATE_QUIZ_MUTATION = read_graphql("tests/graphql/mutations/create_quiz.graphql")


def _setup_staff_and_tenant():
    tenant = TenantModel.objects.create(
        tenant_type=TenantTypeEnum.COMPANY.value,
        name="Acme Inc",
        slug="acme-inc",
    )
    staff_user = MyUser.objects.create_user(
        username="staff",
        email="staff@example.com",
        password="s3cret-pw",
        is_superuser=True,
    )
    UserTenantModel.objects.create(
        user=staff_user,
        tenant=tenant,
        role=UserTenantRoleEnum.ADMIN.value,
        is_active=True,
    )
    return tenant, staff_user


@pytest.mark.asyncio
async def test_create_quiz_success_response_shape(snapshot_json_matcher):
    """Pins the full `create_quiz` GraphQL response shape. `correlation_id`
    (client-supplied) and `payload.id`/`payload.code` (server-generated)
    are legitimately different on every run, so they're matched by type
    instead of exact value — everything else (the response's structure and
    `quiz_type`'s default) is a real regression if it ever changes.

    The `Authorization` token is minted directly with the app's own
    `TokenService` instead of going through the `login` mutation — this
    test's subject is `create_quiz`, not login, so a real signed JWT
    (still decoded by the real `AuthMiddleware`) is enough; it doesn't
    need the extra DB round-trip `login` would add. See
    `tests/account/presentation/schema/test_auth_session_flow.py` for
    where the login flow itself is actually under test."""
    tenant, staff_user = await sync_to_async(
        _setup_staff_and_tenant, thread_sensitive=True
    )()
    token = get_token_service().encode(
        SessionClaims(user_id=staff_user.id, is_staff=True)
    )

    transport = ASGITransport(app=fastapp)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/graph/quizzes/",
            json={
                "query": CREATE_QUIZ_MUTATION,
                "variables": {
                    "tenantId": str(tenant.id),
                    "tenantUserId": str(staff_user.id),
                    "questions": [],
                },
            },
            headers={
                "X-Correlation-ID": str(uuid.uuid4()),
                "X-Operation-ID": str(uuid.uuid4()),
                "Authorization": f"Bearer {token}",
            },
        )

    body = response.json()
    assert response.status_code == 200

    snapshot = snapshot_json_matcher(
        {
            "data.quiz.create_quiz.correlation_id": (str,),
            "data.quiz.create_quiz.payload.id": (str,),
            "data.quiz.create_quiz.payload.code": (str,),
        },
        data=body,
    )
    assert body == snapshot
