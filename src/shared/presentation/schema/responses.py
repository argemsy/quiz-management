from typing import Generic, TypeVar

import strawberry

from src.shared.infrastructure.persistence.django.models import nanoid_generator

_TS = TypeVar("_TS")


def get_operation_id() -> str:
    return nanoid_generator(size=12)


@strawberry.interface
class BaseErrorResponse:
    """Common shape for every typed error response, so a mutation's response
    union can discriminate on `__typename` while sharing operation_id/message.
    """

    operation_id: str
    message: str


@strawberry.type
class ValidationErrorResponse(BaseErrorResponse):
    field: str | None = None


@strawberry.type
class IntegrityErrorResponse(BaseErrorResponse):
    pass


@strawberry.type
class InternalErrorResponse(BaseErrorResponse):
    pass


@strawberry.type
class NotFoundErrorResponse(BaseErrorResponse):
    resource: str


@strawberry.type()
class QuizGenericPayload(Generic[_TS]):
    operation_id: str
    payload: _TS
