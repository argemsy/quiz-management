from django.apps import AppConfig


class AccountConfig(AppConfig):
    name = "src.account"
    label = "account"

    def ready(self):
        import src.account.presentation.admin  # type: ignore
