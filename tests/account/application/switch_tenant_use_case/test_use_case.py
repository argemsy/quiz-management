import uuid

import pytest

from src.account.application.session_claims_service import SessionClaimsService
from src.account.application.switch_tenant_use_case.dto import SwitchTenantDTO
from src.account.application.switch_tenant_use_case.service import (
    SwitchTenantService,
)
from src.account.application.switch_tenant_use_case.use_case import (
    SwitchTenantUseCase,
)
from src.account.domain.entities.user_entity import UserEntity
from src.account.domain.entities.user_tenant_entity import UserTenantEntity
from src.account.domain.exceptions import MembershipNotFoundError
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
) -> SwitchTenantUseCase:
    claims_service = SessionClaimsService(
        fake_user_tenant_repository, fake_permission_version_repository
    )
    return SwitchTenantUseCase(
        SwitchTenantService(fake_user_repository, claims_service), token_service
    )


@pytest.mark.asyncio
async def test_switch_to_a_tenant_the_user_belongs_to(
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
        role=UserTenantRoleEnum.COLLABORATOR,
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
        SwitchTenantDTO(user_id=user.id, tenant_id=tenant_id)
    )

    assert result.active_tenant_id == tenant_id
    assert result.role == "COLLABORATOR"


@pytest.mark.asyncio
async def test_switch_rejected_for_a_tenant_the_user_does_not_belong_to(
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
        await use_case.execute(SwitchTenantDTO(user_id=user.id, tenant_id=uuid.uuid4()))
