import uuid

import pytest

from src.account.application.login_use_case.dto import LoginDTO
from src.account.application.login_use_case.service import LoginService
from src.account.application.login_use_case.use_case import LoginUseCase
from src.account.application.session_claims_service import SessionClaimsService
from src.account.domain.entities.user_entity import UserEntity
from src.account.domain.entities.user_tenant_entity import UserTenantEntity
from src.account.domain.exceptions import (
    InvalidCredentialsError,
    MembershipNotFoundError,
    TenantRequiredError,
)
from src.account.shared.account_enums import UserTenantRoleEnum
from src.shared.infrastructure.auth import TokenService


@pytest.fixture
def token_service() -> TokenService:
    return TokenService(secret_key="test-secret-key", exp_minutes=15)


def _make_use_case(
    fake_user_repository,
    fake_user_tenant_repository,
    fake_permission_version_repository,
    token_service,
) -> LoginUseCase:
    claims_service = SessionClaimsService(
        fake_user_tenant_repository, fake_permission_version_repository
    )
    return LoginUseCase(
        LoginService(fake_user_repository, claims_service), token_service
    )


@pytest.mark.asyncio
async def test_successful_login_with_a_tenant(
    fake_user_repository,
    fake_user_tenant_repository,
    fake_permission_version_repository,
    token_service,
):
    user = UserEntity(id=uuid.uuid4(), email="alice@example.com", is_superuser=False)
    tenant_id = uuid.uuid4()
    membership = UserTenantEntity(
        id=uuid.uuid4(),
        user_id=user.id,
        tenant_id=tenant_id,
        role=UserTenantRoleEnum.ADMIN,
        is_active=True,
    )
    fake_user_repository.add_user(user, password="secret123")
    fake_user_tenant_repository.add_membership(membership)
    use_case = _make_use_case(
        fake_user_repository,
        fake_user_tenant_repository,
        fake_permission_version_repository,
        token_service,
    )

    result = await use_case.execute(
        LoginDTO(email="alice@example.com", password="secret123", tenant_id=tenant_id)
    )

    assert result.is_staff is False
    assert result.active_tenant_id == tenant_id
    assert result.role == "ADMIN"
    decoded = token_service.decode(result.token)
    assert decoded.user_id == user.id
    assert decoded.user_tenant_id == membership.id


@pytest.mark.asyncio
async def test_successful_staff_login_without_a_tenant(
    fake_user_repository,
    fake_user_tenant_repository,
    fake_permission_version_repository,
    token_service,
):
    user = UserEntity(id=uuid.uuid4(), email="staff@example.com", is_superuser=True)
    fake_user_repository.add_user(user, password="secret123")
    use_case = _make_use_case(
        fake_user_repository,
        fake_user_tenant_repository,
        fake_permission_version_repository,
        token_service,
    )

    result = await use_case.execute(
        LoginDTO(email="staff@example.com", password="secret123", tenant_id=None)
    )

    assert result.is_staff is True
    assert result.active_tenant_id is None
    assert result.role is None


@pytest.mark.asyncio
async def test_login_rejected_for_invalid_credentials(
    fake_user_repository,
    fake_user_tenant_repository,
    fake_permission_version_repository,
    token_service,
):
    user = UserEntity(id=uuid.uuid4(), email="alice@example.com", is_superuser=False)
    fake_user_repository.add_user(user, password="secret123")
    use_case = _make_use_case(
        fake_user_repository,
        fake_user_tenant_repository,
        fake_permission_version_repository,
        token_service,
    )

    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(
            LoginDTO(email="alice@example.com", password="wrong", tenant_id=None)
        )


@pytest.mark.asyncio
async def test_login_rejected_for_a_tenant_the_user_does_not_belong_to(
    fake_user_repository,
    fake_user_tenant_repository,
    fake_permission_version_repository,
    token_service,
):
    user = UserEntity(id=uuid.uuid4(), email="alice@example.com", is_superuser=False)
    fake_user_repository.add_user(user, password="secret123")
    use_case = _make_use_case(
        fake_user_repository,
        fake_user_tenant_repository,
        fake_permission_version_repository,
        token_service,
    )

    with pytest.raises(MembershipNotFoundError):
        await use_case.execute(
            LoginDTO(
                email="alice@example.com",
                password="secret123",
                tenant_id=uuid.uuid4(),
            )
        )


@pytest.mark.asyncio
async def test_login_rejected_for_non_staff_user_without_a_tenant(
    fake_user_repository,
    fake_user_tenant_repository,
    fake_permission_version_repository,
    token_service,
):
    user = UserEntity(id=uuid.uuid4(), email="alice@example.com", is_superuser=False)
    fake_user_repository.add_user(user, password="secret123")
    use_case = _make_use_case(
        fake_user_repository,
        fake_user_tenant_repository,
        fake_permission_version_repository,
        token_service,
    )

    with pytest.raises(TenantRequiredError):
        await use_case.execute(
            LoginDTO(email="alice@example.com", password="secret123", tenant_id=None)
        )
