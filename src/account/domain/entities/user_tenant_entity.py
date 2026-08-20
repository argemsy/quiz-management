from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.account.shared.account_enums import UserTenantRoleEnum

if TYPE_CHECKING:
    from src.account.infrastructure.persistence.django.models.user_tenant import (
        UserTenant,
    )


@dataclass(frozen=True)
class UserTenantEntity:
    id: uuid.UUID
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: UserTenantRoleEnum
    is_active: bool

    @classmethod
    def from_model(cls, instance: "UserTenant") -> "UserTenantEntity":
        return cls(
            id=instance.id,
            user_id=instance.user_id,
            tenant_id=instance.tenant_id,
            role=UserTenantRoleEnum(instance.role),
            is_active=instance.is_active,
        )
