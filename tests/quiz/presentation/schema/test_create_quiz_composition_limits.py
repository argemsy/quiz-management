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

MUTATION = read_graphql(
    "tests/graphql/mutations/create_quiz_with_configuration.graphql"
)


@pytest.fixture(autouse=True)
def _reset_redis_registry():
    """The async Redis client is a process-wide singleton bound to the event
    loop that created it, and every asyncio test gets a fresh loop — without
    this the second test in the file reuses a connection attached to a closed
    loop. Same fixture as `test_create_quiz_idempotency.py`."""
    RedisClientRegistry.reset_for_tests()
    yield
    RedisClientRegistry.reset_for_tests()


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


def _question(text: str, choice_count: int = 2) -> dict:
    return {
        "text": text,
        "response_type": "SINGLE",
        "answer_choices": [
            {"text": f"{text}-choice-{index}", "is_correct": index == 0}
            for index in range(choice_count)
        ],
    }


async def _create_quiz(configuration: dict, questions: list[dict]) -> dict:
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
                "query": MUTATION,
                "variables": {
                    "tenantId": str(tenant.id),
                    "tenantUserId": str(staff_user.id),
                    "configuration": configuration,
                    "questions": questions,
                },
            },
            headers={
                "X-Correlation-ID": str(uuid.uuid4()),
                "X-Operation-ID": str(uuid.uuid4()),
                "Authorization": f"Bearer {token}",
            },
        )

    assert response.status_code == 200
    return response.json()["data"]["quiz"]["create_quiz"]


async def _quiz_count() -> int:
    return await sync_to_async(QuizModel.objects.count, thread_sensitive=True)()


@pytest.mark.asyncio
async def test_too_many_questions_is_rejected_before_anything_is_written():
    result = await _create_quiz(
        {"total_questions_allowed": 2},
        [_question(f"q{index}") for index in range(3)],
    )

    assert result["__typename"] == "ValidationErrorResponse"
    assert "at most 2 questions" in result["message"]
    assert await _quiz_count() == 0


@pytest.mark.asyncio
async def test_too_many_answer_choices_is_rejected_before_anything_is_written():
    result = await _create_quiz(
        {"max_answers_allowed": 3},
        [_question("q1"), _question("too-many", choice_count=4)],
    )

    assert result["__typename"] == "ValidationErrorResponse"
    assert "'too-many'" in result["message"]
    assert await _quiz_count() == 0


@pytest.mark.asyncio
async def test_incoherent_configuration_is_a_validation_error_not_an_internal_one():
    """A `ValueError` out of the frozen dataclass would land in the
    decorator's catch-all and surface as `InternalErrorResponse`, telling
    the client nothing about what it sent wrong."""
    result = await _create_quiz(
        {"total_questions_allowed": 5, "min_questions_allowed": 9},
        [_question("q1")],
    )

    assert result["__typename"] == "ValidationErrorResponse"
    assert await _quiz_count() == 0


@pytest.mark.asyncio
async def test_exactly_at_both_limits_is_accepted():
    result = await _create_quiz(
        {"total_questions_allowed": 2, "max_answers_allowed": 3},
        [_question("q1", choice_count=3), _question("q2", choice_count=3)],
    )

    assert result["__typename"] == "CreateQuizSuccess"
    assert await _quiz_count() == 1


@pytest.mark.asyncio
async def test_ordering_strategy_round_trips_through_the_stored_configuration():
    result = await _create_quiz(
        {"question_order": "RANDOM", "answer_order": "RANDOM"},
        [_question("q1")],
    )

    assert result["__typename"] == "CreateQuizSuccess"

    stored = await sync_to_async(
        lambda: QuizModel.objects.get(id=result["payload"]["id"]).configuration,
        thread_sensitive=True,
    )()

    assert stored["question_order"] == "RANDOM"
    assert stored["answer_order"] == "RANDOM"
