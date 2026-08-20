import strawberry

from src.account.presentation.schema.mutations.mutations_admin import AccountMutation


@strawberry.type()
class AccountMutationBuilder(AccountMutation):
    pass
