from src.tenant.infrastructure.persistence.django.models.tenant import (
    Tenant as TenantModel,
)
from src.tenant.infrastructure.persistence.django.models.tenat_user import (
    TenantUser as TenantUserModel,
)

__all__ = [
    "TenantModel",
    "TenantUserModel",
]
