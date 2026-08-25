import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.quiz.domain.exceptions import InvalidAreaHierarchyError

# The taxonomy is deliberately capped at two levels: a root, and its
# children. This is not only a query convenience — it is what makes cycles
# unrepresentable. A cycle of any length needs at least one node that is
# simultaneously someone's child and someone's parent, and `MAX_DEPTH = 2`
# expressed as "a parent must be a root" forbids exactly that. See
# design.md - Decisions (quiz-subject-areas).
MAX_DEPTH = 2


@dataclass(frozen=True)
class AreaEntity:
    name: str
    tenant: uuid.UUID
    tenant_user: uuid.UUID
    id: uuid.UUID | None = None
    parent_id: uuid.UUID | None = None
    is_active: bool = True
    deactivated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise InvalidAreaHierarchyError("An area must have a name")

        if self.id is not None and self.id == self.parent_id:
            raise InvalidAreaHierarchyError("An area cannot be its own parent")

    @property
    def is_root(self) -> bool:
        return self.parent_id is None

    @classmethod
    def from_model(cls, instance: Any) -> "AreaEntity":
        return cls(
            id=instance.id,
            name=instance.name,
            tenant=instance.tenant,
            tenant_user=instance.tenant_user,
            parent_id=instance.parent_id,
            is_active=instance.is_active,
            deactivated_at=instance.deactivated_at,
        )


def ensure_parent_is_root(parent: AreaEntity | None) -> None:
    """Reject a parent that already has a parent of its own.

    Cannot be a database check constraint: it has to read the prospective
    parent's own `parent_id`, which is a different row.

    Args:
        parent: The area proposed as parent, or None for a root area.

    Raises:
        InvalidAreaHierarchyError: `parent` is itself a child, which would
            create a third level.
    """
    if parent is None:
        return

    if not parent.is_root:
        raise InvalidAreaHierarchyError(
            f"Area {parent.name!r} is already a child; areas are limited to "
            f"{MAX_DEPTH} levels"
        )


def ensure_can_become_child(area: AreaEntity, has_children: bool) -> None:
    """Reject giving a parent to an area that already has children.

    The symmetric half of `ensure_parent_is_root`. Without it the cap is
    escapable bottom-up: build "Ciencias" → "Ciencias I" legally, then give
    "Ciencias" a parent and the tree is three deep.

    Args:
        area: The area being given a parent.
        has_children: Whether any area already names it as parent.

    Raises:
        InvalidAreaHierarchyError: The move would create a third level.
    """
    if has_children:
        raise InvalidAreaHierarchyError(
            f"Area {area.name!r} has children and cannot become a child itself; "
            f"areas are limited to {MAX_DEPTH} levels"
        )
