from django.apps import AppConfig


class EventingConfig(AppConfig):
    name = "src.eventing"
    label = "eventing"

    def ready(self):
        import src.eventing.presentation.admin  # type: ignore
        from src.account.shared.account_event_channels import AccountEventChannel
        from src.eventing.application.persist_failed_event_use_case.dto import (
            PersistFailedEventDTO,
        )
        from src.eventing.application.persist_failed_event_use_case.use_case import (
            PersistFailedEventUseCase,
        )
        from src.eventing.infrastructure.event_handlers.audit_event_handlers import (
            handle_account_entity_changed,
        )
        from src.eventing.infrastructure.repositories.failed_event_message_repository_imp import (
            FailedEventMessageRepositoryImpl,
        )
        from src.shared.infrastructure.event_bus import get_event_bus

        persist_use_case = PersistFailedEventUseCase(FailedEventMessageRepositoryImpl())
        get_event_bus().set_failure_sink(
            lambda event, handler, exc: persist_use_case.execute(
                PersistFailedEventDTO.from_event_bus_failure(event, handler, exc)
            )
        )
        get_event_bus().subscribe(
            AccountEventChannel.ENTITY_CHANGED, handle_account_entity_changed
        )
