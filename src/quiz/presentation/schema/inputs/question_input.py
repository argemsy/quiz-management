import strawberry

from src.quiz.presentation.schema.inputs.answer_choice_input import (
    QuizAnswerChoiceInput,
)
from src.quiz.presentation.schema.quiz_enums import StrawberryQuestionTypeEnum


@strawberry.input
class QuizQuestionInput:
    text: str
    response_type: StrawberryQuestionTypeEnum
    answer_choices: list[QuizAnswerChoiceInput]
