import uuid

import pytest

from src.quiz.domain.entities.area_entity import (
    AreaEntity,
    ensure_can_become_child,
    ensure_parent_is_root,
)
from src.quiz.domain.exceptions import InvalidAreaHierarchyError

TENANT = uuid.uuid4()
USER = uuid.uuid4()


def _area(name: str, parent_id=None, area_id=None) -> AreaEntity:
    return AreaEntity(
        name=name,
        tenant=TENANT,
        tenant_user=USER,
        id=area_id or uuid.uuid4(),
        parent_id=parent_id,
    )


def test_root_area_reports_itself_as_root():
    assert _area("Ciencias").is_root


def test_child_area_is_not_root():
    assert not _area("Ciencias I", parent_id=uuid.uuid4()).is_root


def test_area_cannot_be_its_own_parent():
    area_id = uuid.uuid4()

    with pytest.raises(InvalidAreaHierarchyError, match="its own parent"):
        _area("Ciencias", parent_id=area_id, area_id=area_id)


@pytest.mark.parametrize("name", ["", "   "])
def test_area_requires_a_name(name):
    with pytest.raises(InvalidAreaHierarchyError, match="must have a name"):
        _area(name)


def test_a_root_may_be_a_parent():
    ensure_parent_is_root(_area("Ciencias"))


def test_no_parent_is_always_acceptable():
    ensure_parent_is_root(None)


def test_a_child_may_not_be_a_parent():
    """The third level is where a cycle would first become representable, so
    this is the check that keeps the graph acyclic."""
    child = _area("Ciencias I", parent_id=uuid.uuid4())

    with pytest.raises(InvalidAreaHierarchyError, match="already a child"):
        ensure_parent_is_root(child)


def test_an_area_without_children_may_become_a_child():
    ensure_can_become_child(_area("Matemática"), has_children=False)


def test_an_area_with_children_may_not_become_a_child():
    """Without this the cap is escapable bottom-up: build Ciencias →
    Ciencias I legally, then give Ciencias a parent."""
    with pytest.raises(InvalidAreaHierarchyError, match="has children"):
        ensure_can_become_child(_area("Ciencias"), has_children=True)


def test_from_model_reads_the_parent_id_without_touching_the_relation():
    class _FakeAreaModel:
        id = uuid.uuid4()
        name = "Ciencias"
        tenant = TENANT
        tenant_user = USER
        parent_id = None
        is_active = True
        deactivated_at = None

    entity = AreaEntity.from_model(_FakeAreaModel())

    assert entity.name == "Ciencias"
    assert entity.is_root
