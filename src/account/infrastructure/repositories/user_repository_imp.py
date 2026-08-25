from django.contrib.auth import authenticate

from src.account.domain.entities.user_entity import UserEntity
from src.account.domain.repositories.user_repository import UserRepository
from src.account.infrastructure.persistence.django.models import MyUser
from src.shared.domain.specification import Specification
from src.shared.infrastructure.persistence.django.models import async_database
from src.shared.infrastructure.persistence.django.specification import to_django_q


class UserRepositoryImpl(UserRepository):
    """Uses Django's `authenticate()` (default `ModelBackend`, no custom
    backend configured) — pure ORM/hashing, no dependency on
    `request.session` (see design.md - Decisions: Django's password
    hashing is reused, its session-based login is not)."""

    @async_database()
    def authenticate(self, email: str, password: str) -> UserEntity | None:
        user = authenticate(username=email, password=password)
        if user is None:
            return None
        return UserEntity.from_model(user)

    @async_database()
    def find(self, spec: Specification) -> list[UserEntity]:
        queryset = MyUser.objects.filter(to_django_q(spec))
        return [UserEntity.from_model(instance) for instance in queryset]
