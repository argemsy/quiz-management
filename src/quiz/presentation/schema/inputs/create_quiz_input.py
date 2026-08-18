import strawberry

from src.quiz.presentation.schema.inputs.quiz_input import QuizInput


@strawberry.input
class CreateQuizInput:
    tenant_id: strawberry.ID
    tenant_user_id: strawberry.ID
    quiz: QuizInput
