from django.apps import AppConfig


class IdentityConfig(AppConfig):
    name = "src.identity"
    label = "identity"

    def ready(self):
        import src.identity.presentation.admin  # type: ignore
