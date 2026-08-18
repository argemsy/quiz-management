import strawberry
from strawberry.schema.config import StrawberryConfig

from src.quiz.presentation.schema.mutations.mutation_builder import QuizMutationBuilder
from src.shared.presentation.schema.context import Info


@strawberry.type
class Query:
    pass


@strawberry.type
class Mutation:
    @strawberry.mutation
    def quiz(self, info: Info) -> QuizMutationBuilder:
        return QuizMutationBuilder()


schema = strawberry.federation.Schema(
    query=Query,
    mutation=Mutation,
    config=StrawberryConfig(auto_camel_case=False),
)
