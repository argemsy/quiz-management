from django.db.models import Q

from src.shared.domain.specification import (
    AndSpecification,
    FieldFilterSpecification,
    NotSpecification,
    OrSpecification,
    Specification,
)


def to_django_q(spec: Specification) -> Q:
    """Only Django repository implementations call this — the port itself
    (`domain/repositories/*.py`) never imports `Q` or this module."""
    if isinstance(spec, FieldFilterSpecification):
        return Q(**spec.filters)
    if isinstance(spec, AndSpecification):
        return to_django_q(spec.left) & to_django_q(spec.right)
    if isinstance(spec, OrSpecification):
        return to_django_q(spec.left) | to_django_q(spec.right)
    if isinstance(spec, NotSpecification):
        return ~to_django_q(spec.spec)
    raise TypeError(f"Unsupported specification type: {type(spec)!r}")
