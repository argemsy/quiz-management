import asyncio
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
from src.quiz.infrastructure.persistence.django.models import QuizModel
from src.shared.infrastructure.auth import SessionClaims, get_token_service
from src.shared.infrastructure.cache import RedisClientRegistry
from tests.tools.graphql import read_graphql

pytestmark = pytest.mark.django_db(transaction=True)

CREATE_QUIZ_MUTATION = read_graphql("tests/graphql/mutations/create_quiz.graphql")


@pytest.fixture(autouse=True)
def _reset_redis_registry():
    RedisClientRegistry.reset_for_tests()
    yield
    RedisClientRegistry.reset_for_tests()


def _headers(*, correlation_id: str, operation_id: str, token: str) -> dict:
    return {
        "X-Correlation-ID": correlation_id,
        "X-Operation-ID": operation_id,
        "Authorization": f"Bearer {token}",
    }


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


def _token_for(staff_user) -> str:
    """Mints a real, app-signed JWT directly instead of going through the
    `login` mutation — these tests are about `create_quiz` idempotency,
    not login, so a valid `Authorization` token (still decoded by the real
    `AuthMiddleware`) is enough without the extra DB round-trip `login`
    would add per test."""
    return get_token_service().encode(
        SessionClaims(user_id=staff_user.id, is_staff=True)
    )


async def _create_quiz(client, token, tenant, staff_user, operation_id, questions=None):
    return await client.post(
        "/api/graph/quizzes/",
        json={
            "query": CREATE_QUIZ_MUTATION,
            "variables": {
                "tenantId": str(tenant.id),
                "tenantUserId": str(staff_user.id),
                "questions": questions or [],
            },
        },
        headers=_headers(
            correlation_id=str(uuid.uuid4()), operation_id=operation_id, token=token
        ),
    )


@pytest.mark.asyncio
async def test_duplicate_operation_id_after_success_replays_without_a_new_row():
    tenant, staff_user = await sync_to_async(
        _setup_staff_and_tenant, thread_sensitive=True
    )()

    transport = ASGITransport(app=fastapp)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = _token_for(staff_user)
        operation_id = str(uuid.uuid4())

        first = await _create_quiz(client, token, tenant, staff_user, operation_id)
        second = await _create_quiz(client, token, tenant, staff_user, operation_id)

    assert first.status_code == 200
    assert second.status_code == 200
    first_payload = first.json()["data"]["quiz"]["create_quiz"]
    second_payload = second.json()["data"]["quiz"]["create_quiz"]
    assert first_payload["__typename"] == "CreateQuizSuccess"
    assert second_payload["__typename"] == "CreateQuizSuccess"
    assert first_payload["payload"]["id"] == second_payload["payload"]["id"]

    quiz_count = await sync_to_async(QuizModel.objects.count, thread_sensitive=True)()
    assert quiz_count == 1


@pytest.mark.asyncio
async def test_concurrent_duplicate_operation_id_creates_at_most_one_row():
    tenant, staff_user = await sync_to_async(
        _setup_staff_and_tenant, thread_sensitive=True
    )()

    transport = ASGITransport(app=fastapp)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = _token_for(staff_user)
        operation_id = str(uuid.uuid4())

        responses = await asyncio.gather(
            _create_quiz(client, token, tenant, staff_user, operation_id),
            _create_quiz(client, token, tenant, staff_user, operation_id),
            _create_quiz(client, token, tenant, staff_user, operation_id),
        )

    assert all(r.status_code == 200 for r in responses)
    typenames = [
        r.json()["data"]["quiz"]["create_quiz"]["__typename"] for r in responses
    ]
    # Every response is either the replayed success or the "already being
    # processed" fast-path rejection — never a second independent success
    # that could indicate a second row.
    assert set(typenames) <= {"CreateQuizSuccess", "IntegrityErrorResponse"}

    quiz_count = await sync_to_async(QuizModel.objects.count, thread_sensitive=True)()
    assert quiz_count == 1


@pytest.mark.asyncio
async def test_different_operation_ids_create_separate_rows():
    tenant, staff_user = await sync_to_async(
        _setup_staff_and_tenant, thread_sensitive=True
    )()

    transport = ASGITransport(app=fastapp)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = _token_for(staff_user)

        first = await _create_quiz(client, token, tenant, staff_user, str(uuid.uuid4()))
        second = await _create_quiz(
            client, token, tenant, staff_user, str(uuid.uuid4())
        )

    first_payload = first.json()["data"]["quiz"]["create_quiz"]
    second_payload = second.json()["data"]["quiz"]["create_quiz"]
    assert first_payload["__typename"] == "CreateQuizSuccess"
    assert second_payload["__typename"] == "CreateQuizSuccess"
    assert first_payload["payload"]["id"] != second_payload["payload"]["id"]

    quiz_count = await sync_to_async(QuizModel.objects.count, thread_sensitive=True)()
    assert quiz_count == 2


@pytest.mark.asyncio
async def test_duplicate_detection_holds_when_redis_fast_path_is_unavailable(
    monkeypatch,
):
    import redis.asyncio as redis_asyncio

    tenant, staff_user = await sync_to_async(
        _setup_staff_and_tenant, thread_sensitive=True
    )()

    unreachable_client = redis_asyncio.from_url(
        "redis://localhost:1/0",
        socket_timeout=0.2,
        socket_connect_timeout=0.2,
        decode_responses=True,
    )
    monkeypatch.setattr(
        "src.shared.infrastructure.cache.idempotency_lock.get_redis_client",
        lambda: unreachable_client,
    )

    transport = ASGITransport(app=fastapp)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = _token_for(staff_user)
        operation_id = str(uuid.uuid4())

        first = await _create_quiz(client, token, tenant, staff_user, operation_id)
        second = await _create_quiz(client, token, tenant, staff_user, operation_id)

    first_payload = first.json()["data"]["quiz"]["create_quiz"]
    second_payload = second.json()["data"]["quiz"]["create_quiz"]
    assert first_payload["__typename"] == "CreateQuizSuccess"
    assert second_payload["__typename"] == "CreateQuizSuccess"
    assert first_payload["payload"]["id"] == second_payload["payload"]["id"]

    quiz_count = await sync_to_async(QuizModel.objects.count, thread_sensitive=True)()
    assert quiz_count == 1
    await unreachable_client.aclose()


@pytest.mark.asyncio
async def test_question_with_no_answer_choices_returns_a_validation_error():
    """`QuestionEntity`'s invariant (`InvalidQuestionError`, a `DomainError`
    subclass) must surface as `ValidationErrorResponse`, not
    `InternalErrorResponse` — see use-case-service-boundary proposal.md -
    Why."""
    tenant, staff_user = await sync_to_async(
        _setup_staff_and_tenant, thread_sensitive=True
    )()

    transport = ASGITransport(app=fastapp)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = _token_for(staff_user)
        response = await _create_quiz(
            client,
            token,
            tenant,
            staff_user,
            str(uuid.uuid4()),
            questions=[
                {
                    "text": "No answer choices",
                    "response_type": "SINGLE",
                    "answer_choices": [],
                }
            ],
        )

    assert response.status_code == 200
    payload = response.json()["data"]["quiz"]["create_quiz"]
    assert payload["__typename"] == "ValidationErrorResponse"

    quiz_count = await sync_to_async(QuizModel.objects.count, thread_sensitive=True)()
    assert quiz_count == 0
