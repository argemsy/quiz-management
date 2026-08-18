import uuid

from src.account.infrastructure.persistence.django.models import (
    TenantModel,
    UserTenantModel,
)
from src.quiz.domain.repositories.tenant_lookup_repository import TenantLookupRepository
from src.shared.infrastructure.persistence.django.models import async_database


class TenantLookupRepositoryImpl(TenantLookupRepository):
    """account app's implementation of the TenantLookupRepository port.

    Quiz defines the port (what it needs to know about tenants).
    Account implements it (how to query its own models).
    This keeps quiz free from account model imports.
    """

    @async_database()
    def tenant_exists(self, tenant_id: uuid.UUID) -> bool:
        return TenantModel.objects.filter(
            id=tenant_id, is_active=True, is_deleted=False
        ).exists()

    @async_database()
    def tenant_user_exists(
        self, tenant_id: uuid.UUID, tenant_user_id: uuid.UUID
    ) -> bool:
        return UserTenantModel.objects.filter(
            tenant_id=tenant_id,
            user_id=tenant_user_id,
            is_active=True,
            is_deleted=False,
        ).exists()
