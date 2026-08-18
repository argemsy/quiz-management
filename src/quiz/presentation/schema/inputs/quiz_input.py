import strawberry

from src.quiz.presentation.schema.inputs.question_input import QuizQuestionInput
from src.quiz.presentation.schema.quiz_enums import StrawberryQuizTypeEnum


@strawberry.input
class QuizConfigurationInput:
    total_questions_allowed: int = 20
    time_limit_minutes: int = 60
    allow_review: bool = True
    allowed_attempts: int | None = None


@strawberry.input
class QuizInput:
    quiz_type: StrawberryQuizTypeEnum = StrawberryQuizTypeEnum.PRACTICE
    configuration: QuizConfigurationInput = strawberry.field(
        default_factory=QuizConfigurationInput
    )
    questions: list[QuizQuestionInput]
