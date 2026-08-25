import strawberry
from strawberry.schema.config import StrawberryConfig

from src.account.presentation.schema.mutations.mutation_builder import (
    AccountMutationBuilder,
)
from src.quiz.presentation.schema.mutations.mutation_builder import QuizMutationBuilder
from src.shared.presentation.schema.context import Info
from src.shared.presentation.schema.types import JSONType


@strawberry.type
class Query:
    pass


@strawberry.type
class Mutation:
    @strawberry.mutation
    def quiz(self, info: Info) -> QuizMutationBuilder:
        return QuizMutationBuilder()

    @strawberry.mutation
    def account(self, info: Info) -> AccountMutationBuilder:
        return AccountMutationBuilder()


schema = strawberry.federation.Schema(
    query=Query,
    mutation=Mutation,
    config=StrawberryConfig(
        auto_camel_case=False,
        scalar_map={
            JSONType: strawberry.scalar(
                name="JSON",
                description=(
                    "The `JSON` scalar type represents JSON values as specified by ECMA-404"
                ),
                serialize=lambda v: v,
                parse_value=lambda v: v,
            )
        },
    ),
)
