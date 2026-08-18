from django.contrib import admin

from src.eventing.application.retry_failed_event_use_case.dto import RetryFailedEventDTO
from src.eventing.application.retry_failed_event_use_case.use_case import (
    RetryFailedEventUseCase,
)
from src.eventing.infrastructure.persistence.django.models import FailedEventMessage
from src.eventing.infrastructure.repositories.failed_event_message_repository_imp import (
    FailedEventMessageRepositoryImpl,
)


@admin.register(FailedEventMessage)
class FailedEventMessageAdmin(admin.ModelAdmin):
    list_display = (
        "resource_name",
        "channel_path",
        "status",
        "retry_count",
        "correlation_id",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("resource_name", "correlation_id", "channel_path", "handler_path")
    readonly_fields = (
        "id",
        "channel_path",
        "handler_path",
        "correlation_id",
        "payload",
        "metadata",
        "error_type",
        "error_message",
        "retry_count",
        "created_at",
        "updated_at",
    )
    actions = ["retry_selected"]

    @admin.action(description="Retry selected")
    def retry_selected(self, request, queryset):
        use_case = RetryFailedEventUseCase(FailedEventMessageRepositoryImpl())
        succeeded = 0
        failed = 0
        for failed_event in queryset:
            try:
                use_case.execute(RetryFailedEventDTO(failed_event_id=failed_event.id))
                succeeded += 1
            except Exception:  # noqa: BLE001
                failed += 1
        self.message_user(
            request, f"{succeeded} retried successfully, {failed} failed again."
        )
