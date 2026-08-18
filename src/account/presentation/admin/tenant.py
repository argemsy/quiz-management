from django.contrib import admin

from src.account.infrastructure.persistence.django.models import TenantModel
from src.shared.presentation.admin import CommonAdminActionsMixin


@admin.register(TenantModel)
class TenantAdmin(CommonAdminActionsMixin, admin.ModelAdmin):
    list_display = ("name", "tenant_type", "slug", "is_active", "is_deleted")
    list_filter = ("tenant_type", "is_active", "is_deleted")
    search_fields = ("name", "slug")
    readonly_fields = ("id", "slug", "created_at", "updated_at")
