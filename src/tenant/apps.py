from django.apps import AppConfig


class TenantConfig(AppConfig):
    name = "src.tenant"
    label = "tenant"

    def ready(self):
        import src.tenant.presentation.admin  # type: ignore
