from django.contrib import admin

from src.shared.presentation.admin import CommonAdminActionsMixin
from src.tenant.infrastructure.persistence.django.models import TenantUserModel


@admin.register(TenantUserModel)
class TenantUserAdmin(CommonAdminActionsMixin, admin.ModelAdmin):
    list_display = ("user", "tenant", "role", "is_active", "is_deleted")
    list_filter = ("role", "is_active", "is_deleted")
    search_fields = ("user",)
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "activated_at",
        "deactivated_at",
    )
