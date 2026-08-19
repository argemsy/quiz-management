from abc import ABC, abstractmethod

from src.account.domain.entities.user_entity import UserEntity
from src.shared.domain.specification import Specification


class UserRepository(ABC):
    @abstractmethod
    async def authenticate(self, email: str, password: str) -> UserEntity | None:
        """Verifies credentials and returns the matching user, or None if
        the email/password combination does not authenticate. Not
        spec-based: this delegates to Django's `authenticate()` backend
        call, which has fixed two-argument semantics — there's no growing
        set of filter combinations here to warrant the Specification
        pattern (see `find`, which is)."""

    @abstractmethod
    async def find(self, spec: Specification) -> list[UserEntity]:
        pass
