from django.contrib import admin

from src.eventing.infrastructure.persistence.django.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "content_type",
        "action_type",
        "source_type",
        "object_id",
        "tenant",
        "user",
        "created_at",
    )
    list_filter = ("content_type", "action_type", "source_type")
    search_fields = ("object_id", "object_repr", "user", "tenant", "correlation_id")
    readonly_fields = tuple(field.name for field in AuditLog._meta.get_fields())

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
