import uuid

import pytest
from asgiref.sync import sync_to_async
from django.utils import timezone

from src.quiz.domain.entities.area_entity import AreaEntity
from src.quiz.infrastructure.repositories.area_repository_imp import AreaRepositoryImpl

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.asyncio
async def test_find_active_resolves_a_root_by_identity(make_area):
    area = await sync_to_async(make_area, thread_sensitive=True)(name="Ciencias")

    found = await AreaRepositoryImpl().find_active(area.tenant, "Ciencias", None)

    assert found is not None
    assert found.id == area.id
    assert found.is_root


@pytest.mark.asyncio
async def test_find_active_distinguishes_by_parent(make_area):
    def _setup():
        ciencias = make_area(name="Ciencias")
        matematica = make_area(
            name="Matemática",
            tenant=ciencias.tenant,
            tenant_user=ciencias.tenant_user,
        )
        return (
            ciencias,
            make_area(name="General", parent=ciencias),
            make_area(name="General", parent=matematica),
        )

    ciencias, under_ciencias, _ = await sync_to_async(_setup, thread_sensitive=True)()

    found = await AreaRepositoryImpl().find_active(
        ciencias.tenant, "General", ciencias.id
    )

    assert found.id == under_ciencias.id


@pytest.mark.asyncio
async def test_find_active_ignores_deactivated_areas(make_area):
    """Filtered to active rows to match the uniqueness constraint — an
    inactive area is one the constraint does not consider to exist, so
    returning it would report a collision the database would not raise."""

    def _setup():
        area = make_area(name="Ciencias")
        area.is_active = False
        area.deactivated_at = timezone.now()
        area.save(update_fields=["is_active", "deactivated_at"])
        return area

    area = await sync_to_async(_setup, thread_sensitive=True)()

    assert await AreaRepositoryImpl().find_active(area.tenant, "Ciencias", None) is None


@pytest.mark.asyncio
async def test_find_active_returns_none_when_nothing_matches(make_area):
    area = await sync_to_async(make_area, thread_sensitive=True)(name="Ciencias")

    assert await AreaRepositoryImpl().find_active(area.tenant, "Historia", None) is None


@pytest.mark.asyncio
async def test_has_children_reflects_the_hierarchy(make_area):
    def _setup():
        root = make_area(name="Ciencias")
        return root, make_area(name="Ciencias I", parent=root)

    root, child = await sync_to_async(_setup, thread_sensitive=True)()
    repository = AreaRepositoryImpl()

    assert await repository.has_children(root.id) is True
    assert await repository.has_children(child.id) is False


@pytest.mark.asyncio
async def test_create_persists_a_child_area(make_area):
    root = await sync_to_async(make_area, thread_sensitive=True)(name="Ciencias")

    created = await AreaRepositoryImpl().create(
        AreaEntity(
            name="Ciencias I",
            tenant=root.tenant,
            tenant_user=root.tenant_user,
            parent_id=root.id,
        )
    )

    assert created.id is not None
    assert created.parent_id == root.id
    assert not created.is_root


@pytest.mark.asyncio
async def test_get_by_id_returns_none_for_an_unknown_area():
    assert await AreaRepositoryImpl().get_by_id(uuid.uuid4()) is None
