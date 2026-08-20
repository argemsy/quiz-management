from django.contrib import admin

from src.account.infrastructure.persistence.django.models import UserTenantModel
from src.shared.presentation.admin import CommonAdminActionsMixin


@admin.register(UserTenantModel)
class UserTenantAdmin(CommonAdminActionsMixin, admin.ModelAdmin):
    list_display = ("user", "tenant", "role", "is_active", "is_deleted")
    list_filter = ("role", "is_active", "is_deleted")
    search_fields = ("user__email", "user__username")
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "activated_at",
        "deactivated_at",
    )
