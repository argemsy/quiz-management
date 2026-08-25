import uuid

from django.contrib import admin

from src.account.infrastructure.persistence.django.models import UserTenantModel
from src.account.presentation.admin.mixins import AuditableAdminMixin
from src.eventing.shared.eventing_enums import AuditLogContentTypeEnum
from src.shared.presentation.admin import CommonAdminActionsMixin


@admin.register(UserTenantModel)
class UserTenantAdmin(AuditableAdminMixin, CommonAdminActionsMixin, admin.ModelAdmin):
    audit_content_type = AuditLogContentTypeEnum.TENANT_USER
    list_display = ("user", "tenant", "role", "is_active", "is_deleted")
    list_filter = ("role", "is_active", "is_deleted")
    search_fields = ("user__email", "user__username")
    raw_id_fields = (
        "user",
        "tenant",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "activated_at",
        "deactivated_at",
    )

    def _resolve_audit_tenant(self, obj) -> uuid.UUID | None:
        return obj.tenant_id
