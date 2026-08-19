from django.apps import AppConfig


class AccountConfig(AppConfig):
    name = "src.account"
    label = "account"

    def ready(self):
        import src.account.presentation.admin  # type: ignore
        from src.account.infrastructure.event_handlers.permission_invalidation import (
            handle_entity_changed_for_permissions,
        )
        from src.account.shared.account_event_channels import AccountEventChannel
        from src.shared.infrastructure.event_bus import get_event_bus

        get_event_bus().subscribe(
            AccountEventChannel.ENTITY_CHANGED, handle_entity_changed_for_permissions
        )
