import uuid
from abc import ABC, abstractmethod

from src.quiz.domain.entities.area_entity import AreaEntity


class AreaRepository(ABC):
    @abstractmethod
    async def get_by_id(self, area_id: uuid.UUID) -> AreaEntity | None:
        pass

    @abstractmethod
    async def find_active(
        self,
        tenant: uuid.UUID,
        name: str,
        parent_id: uuid.UUID | None,
    ) -> AreaEntity | None:
        """Resolve an area by the fields that make up its identity.

        Filtered to active areas, matching the uniqueness constraint: an
        inactive area is one the constraint does not consider to exist, so
        returning it here would report a collision the database would not
        actually raise.
        """

    @abstractmethod
    async def has_children(self, area_id: uuid.UUID) -> bool:
        """Whether any area names this one as parent.

        Feeds `ensure_can_become_child`, which needs it to stop the
        two-level cap being escaped bottom-up.
        """

    @abstractmethod
    async def create(self, area: AreaEntity) -> AreaEntity:
        pass
