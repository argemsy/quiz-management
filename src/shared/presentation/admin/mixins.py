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


class TenantScopedInlineAdminMixin:
    """Copies `tenant`/`tenant_user` onto new inline rows from their parent.

    Both fields are `editable=False` and NOT NULL on every tenant-scoped
    model, so they never appear in an inline's form and a row created through
    one would fail the NOT NULL constraint. The parent object is the only
    source the admin has — it carries no notion of which tenant the session
    is acting for.
    """

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if getattr(instance, "tenant", None) is None:
                instance.tenant = form.instance.tenant
                instance.tenant_user = form.instance.tenant_user
            instance.save()
        for obj in formset.deleted_objects:
            obj.delete()
        formset.save_m2m()
