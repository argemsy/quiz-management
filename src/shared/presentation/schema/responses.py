from typing import Generic, TypeVar

import strawberry

_TS = TypeVar("_TS")


@strawberry.interface
class BaseErrorResponse:
    """Common shape for every typed error response, so a mutation's response
    union can discriminate on `__typename` while sharing correlation_id/message.
    """

    correlation_id: str
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
    correlation_id: str
    payload: _TS
