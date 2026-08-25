import uuid

from src.quiz.domain.entities.area_entity import AreaEntity
from src.quiz.domain.repositories.area_repository import AreaRepository
from src.quiz.infrastructure.persistence.django.models import AreaModel
from src.shared.infrastructure.persistence.django.models import async_database


class AreaRepositoryImpl(AreaRepository):
    @async_database()
    def get_by_id(self, area_id: uuid.UUID) -> AreaEntity | None:
        area = AreaModel.objects.filter(id=area_id).first()
        return AreaEntity.from_model(area) if area else None

    @async_database()
    def find_active(
        self,
        tenant: uuid.UUID,
        name: str,
        parent_id: uuid.UUID | None,
    ) -> AreaEntity | None:
        area = AreaModel.objects.filter(
            tenant=tenant,
            name=name,
            parent_id=parent_id,
            is_active=True,
        ).first()
        return AreaEntity.from_model(area) if area else None

    @async_database()
    def has_children(self, area_id: uuid.UUID) -> bool:
        return AreaModel.objects.filter(parent_id=area_id).exists()

    @async_database()
    def create(self, area: AreaEntity) -> AreaEntity:
        created = AreaModel.objects.create(
            name=area.name,
            parent_id=area.parent_id,
            tenant=area.tenant,
            tenant_user=area.tenant_user,
        )
        return AreaEntity.from_model(created)
