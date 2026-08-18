from typing import Type

import strawberry

from src.quiz.shared.quiz_enums import QuestionResponseTypeEnum, QuizTypeEnum

StrawberryQuizTypeEnum: Type[QuizTypeEnum] = strawberry.enum(
    QuizTypeEnum, name="QuizTypeEnum"
)

StrawberryQuestionTypeEnum: Type[QuestionResponseTypeEnum] = strawberry.enum(
    QuestionResponseTypeEnum, name="QuestionResponseTypeEnum"
)
