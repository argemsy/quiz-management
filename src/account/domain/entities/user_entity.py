from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.account.infrastructure.persistence.django.models.user import MyUser


@dataclass(frozen=True)
class UserEntity:
    id: uuid.UUID
    email: str
    is_superuser: bool

    @classmethod
    def from_model(cls, instance: "MyUser") -> "UserEntity":
        return cls(
            id=instance.id,
            email=instance.email,
            is_superuser=instance.is_superuser,
        )
