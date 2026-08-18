import uuid

from src.quiz.domain.repositories.tenant_lookup_repository import TenantLookupRepository
from src.shared.infrastructure.persistence.django.models import async_database
from src.tenant.infrastructure.persistence.django.models import (
    TenantModel,
    TenantUserModel,
)


class TenantLookupRepositoryImpl(TenantLookupRepository):
    @async_database()
    def tenant_exists(self, tenant_id: uuid.UUID) -> bool:
        return TenantModel.objects.filter(
            id=tenant_id, is_active=True, is_deleted=False
        ).exists()

    @async_database()
    def tenant_user_exists(
        self, tenant_id: uuid.UUID, tenant_user_id: uuid.UUID
    ) -> bool:
        return TenantUserModel.objects.filter(
            tenant_id=tenant_id,
            user=tenant_user_id,
            is_active=True,
            is_deleted=False,
        ).exists()
