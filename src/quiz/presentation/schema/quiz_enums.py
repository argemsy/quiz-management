from typing import Type

import strawberry

from src.quiz.shared.quiz_enums import (
    OrderStrategyEnum,
    QuestionResponseTypeEnum,
    QuizTypeEnum,
)

StrawberryQuizTypeEnum: Type[QuizTypeEnum] = strawberry.enum(
    QuizTypeEnum, name="QuizTypeEnum"
)

StrawberryQuestionTypeEnum: Type[QuestionResponseTypeEnum] = strawberry.enum(
    QuestionResponseTypeEnum, name="QuestionResponseTypeEnum"
)

StrawberryOrderStrategyEnum: Type[OrderStrategyEnum] = strawberry.enum(
    OrderStrategyEnum, name="OrderStrategyEnum"
)
