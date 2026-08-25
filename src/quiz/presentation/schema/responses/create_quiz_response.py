from typing import Annotated, Union

import strawberry

from src.quiz.presentation.schema.types.quiz_type import QuizType
from src.shared.presentation.schema.responses import (
    IntegrityErrorResponse,
    InternalErrorResponse,
    QuizGenericPayload,
    ValidationErrorResponse,
)


@strawberry.type(name="CreateQuizSuccess")
class CreateQuizPayload(QuizGenericPayload[QuizType]):
    pass


CreateQuizResponse = Annotated[
    Union[
        ValidationErrorResponse,
        IntegrityErrorResponse,
        InternalErrorResponse,
        CreateQuizPayload,
    ],
    strawberry.union("CreateQuizResponse"),
]
