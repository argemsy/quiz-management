from src.account.domain.entities.user_tenant_entity import UserTenantEntity
from src.account.domain.repositories.user_tenant_repository import (
    UserTenantRepository,
)
from src.account.infrastructure.persistence.django.models import UserTenantModel
from src.shared.domain.specification import Specification
from src.shared.infrastructure.persistence.django.models import async_database
from src.shared.infrastructure.persistence.django.specification import to_django_q


class UserTenantRepositoryImpl(UserTenantRepository):
    @async_database()
    def find(self, spec: Specification) -> list[UserTenantEntity]:
        """Soft-deleted rows are excluded unconditionally — `is_deleted` is
        a persistence concept `UserTenantEntity` doesn't carry, so it isn't
        something a caller-built `spec` can express; this repository
        applies it as its own baseline scope on every read."""
        queryset = UserTenantModel.objects.filter(is_deleted=False).filter(
            to_django_q(spec)
        )
        return [UserTenantEntity.from_model(instance) for instance in queryset]
