from django.contrib import admin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class ActivableAdminMixin:
    """Bulk activate/deactivate actions for models using QuizActiveMixin."""

    actions = ["activate_instances", "deactivate_instances"]

    @admin.action(description=_("Activate selected"))
    def activate_instances(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} instance(s) activated.")

    @admin.action(description=_("Deactivate selected"))
    def deactivate_instances(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} instance(s) deactivated.")


class SoftDeleteAdminMixin:
    """Bulk soft-delete/restore actions for models using QuizSoftDeleteMixin."""

    actions = ["soft_delete_instances", "restore_instances"]

    @admin.action(description=_("Delete selected (soft delete)"))
    def soft_delete_instances(self, request, queryset):
        updated = queryset.update(is_deleted=True, deleted_at=timezone.now())
        self.message_user(request, f"{updated} instance(s) soft-deleted.")

    @admin.action(description=_("Restore selected"))
    def restore_instances(self, request, queryset):
        updated = queryset.update(is_deleted=False, deleted_at=None)
        self.message_user(request, f"{updated} instance(s) restored.")


class CommonAdminActionsMixin(ActivableAdminMixin, SoftDeleteAdminMixin):
    """Combines activate/deactivate + soft-delete/restore bulk actions."""

    actions = ActivableAdminMixin.actions + SoftDeleteAdminMixin.actions
