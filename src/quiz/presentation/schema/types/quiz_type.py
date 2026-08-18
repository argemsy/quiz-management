import strawberry

from src.quiz.domain.entities.quiz_entity import QuizEntity
from src.quiz.presentation.schema.quiz_enums import StrawberryQuizTypeEnum
from src.shared.presentation.schema.context import Info


@strawberry.type
class QuizType:
    value: strawberry.Private[QuizEntity]

    @strawberry.field(name="id")
    def get_id(self, info: Info) -> strawberry.ID:
        return strawberry.ID(self.value.id)

    @strawberry.field(name="code")
    def get_code(self, info: Info) -> strawberry.ID:
        return strawberry.ID(self.value.code)

    @strawberry.field(name="quiz_type")
    def get_quiz_type(self, info: Info) -> StrawberryQuizTypeEnum:
        return self.value.quiz_type
