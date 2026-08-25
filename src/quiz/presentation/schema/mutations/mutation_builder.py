import strawberry

from src.quiz.presentation.schema.mutations.mutations_admin import QuizAdminMutation


@strawberry.type()
class QuizMutationBuilder(QuizAdminMutation):
    pass
