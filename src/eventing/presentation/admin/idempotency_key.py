from django.contrib import admin

from src.eventing.infrastructure.persistence.django.models import IdempotencyKey


@admin.register(IdempotencyKey)
class IdempotencyKeyAdmin(admin.ModelAdmin):
    list_display = ("operation_id", "status", "created_at", "updated_at")
    list_filter = ("status",)
    search_fields = ("operation_id",)
    readonly_fields = (
        "id",
        "operation_id",
        "status",
        "response_payload",
        "created_at",
        "updated_at",
    )
