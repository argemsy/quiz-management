from abc import ABC
from typing import Any


class Specification(ABC):
    """Composable filter criteria, built by application services and
    executed by a repository — repos expose `find(spec)` instead of one
    hand-written query method per filter combination. Django-free by
    design: only `src/shared/infrastructure/persistence/django/specification.py`
    knows how to turn one of these into a `Q`, so a non-Django repository
    implementation (e.g. a future OpenSearch-backed one) can satisfy the
    same port without importing Django."""

    def __and__(self, other: "Specification") -> "AndSpecification":
        return AndSpecification(self, other)

    def __or__(self, other: "Specification") -> "OrSpecification":
        return OrSpecification(self, other)

    def __invert__(self) -> "NotSpecification":
        return NotSpecification(self)


class FieldFilterSpecification(Specification):
    """Leaf: plain field-lookup kwargs. Django lookup suffixes (`__gte`,
    `__in`, etc.) pass through untouched to the ORM once translated, since
    the translator just forwards them to `Q(**filters)`."""

    def __init__(self, **filters: Any) -> None:
        self.filters = filters


class AndSpecification(Specification):
    def __init__(self, left: Specification, right: Specification) -> None:
        self.left = left
        self.right = right


class OrSpecification(Specification):
    def __init__(self, left: Specification, right: Specification) -> None:
        self.left = left
        self.right = right


class NotSpecification(Specification):
    def __init__(self, spec: Specification) -> None:
        self.spec = spec
