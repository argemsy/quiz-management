from abc import ABC, abstractmethod

from src.account.domain.entities.user_tenant_entity import UserTenantEntity
from src.shared.domain.specification import Specification


class UserTenantRepository(ABC):
    @abstractmethod
    async def find(self, spec: Specification) -> list[UserTenantEntity]:
        pass
