import uuid

from src.account.domain.entities.user_entity import UserEntity
from src.account.domain.exceptions import MembershipNotFoundError
from src.account.domain.repositories.permission_version_repository import (
    PermissionVersionRepository,
)
from src.account.domain.repositories.user_tenant_repository import (
    UserTenantRepository,
)
from src.shared.domain.specification import FieldFilterSpecification
from src.shared.infrastructure.auth import SessionClaims


class SessionClaimsService:
    """Shared by `login_use_case`, `switch_tenant_use_case`, and
    `refresh_session_use_case` — all three end with the same job: resolve
    a user's active membership in one tenant (or none, for a staff-only
    session) and assemble the `SessionClaims` a token gets minted from.
    Not nested in one use case's folder since it's genuinely shared, not
    owned by any single one of them."""

    def __init__(
        self,
        user_tenant_repository: UserTenantRepository,
        permission_version_repository: PermissionVersionRepository,
    ) -> None:
        self.user_tenant_repository = user_tenant_repository
        self.permission_version_repository = permission_version_repository

    async def assemble(
        self, user: UserEntity, tenant_id: uuid.UUID | None
    ) -> SessionClaims:
        membership = None
        if tenant_id is not None:
            membership = await self._find_active_membership(user.id, tenant_id)
            if membership is None:
                raise MembershipNotFoundError(tenant_id)

        user_version = await self.permission_version_repository.get_user_version(
            user.id
        )
        user_tenant_version = 0
        if membership is not None:
            user_tenant_version = (
                await self.permission_version_repository.get_user_tenant_version(
                    membership.id
                )
            )

        return SessionClaims(
            user_id=user.id,
            is_staff=user.is_superuser,
            active_tenant_id=membership.tenant_id if membership else None,
            user_tenant_id=membership.id if membership else None,
            role=membership.role.value if membership else None,
            user_version=user_version,
            user_tenant_version=user_tenant_version,
        )

    async def _find_active_membership(self, user_id: uuid.UUID, tenant_id: uuid.UUID):
        """Only `user_id`/`tenant_id`/`is_active` — all fields `UserTenantEntity`
        actually carries. Excluding soft-deleted rows is the repository
        implementation's own baseline scope (an infrastructure concern,
        `UserTenantModel.is_deleted` has no domain-entity equivalent), not
        something this application-layer spec should need to know about."""
        spec = FieldFilterSpecification(
            user_id=user_id, tenant_id=tenant_id, is_active=True
        )
        results = await self.user_tenant_repository.find(spec)
        return results[0] if results else None
