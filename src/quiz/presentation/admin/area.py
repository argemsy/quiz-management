from asgiref.sync import async_to_sync
from django import forms
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from src.account.infrastructure.repositories import TenantLookupRepositoryImpl
from src.quiz.domain.entities.area_entity import AreaEntity, ensure_parent_is_root
from src.quiz.domain.exceptions import InvalidAreaHierarchyError
from src.quiz.infrastructure.persistence.django.models import AreaModel
from src.shared.presentation.admin import ActivableAdminMixin


class AreaAdminForm(forms.ModelForm):
    """Adds `tenant` back as an explicit form field.

    `AreaModel.tenant` is `editable=False` and NOT NULL, so a plain ModelForm
    omits it and every save fails the constraint — and unlike `Quiz`, an area
    has no mutation to create it, so the admin failing means areas cannot be
    created at all. The field stays non-editable on the model (nothing else
    should mass-assign it) and is reintroduced here, where the author is the
    one supplying it.

    A free UUID input rather than a dropdown of tenants: `quiz` does not own
    that data and must not import `account`'s models (mandatory pattern #2).
    It is validated through `TenantLookupRepository`, the port that already
    exists for exactly this.
    """

    tenant = forms.UUIDField(
        label=_("Tenant"),
        help_text=_("UUID of the organization this area belongs to."),
    )

    class Meta:
        model = AreaModel
        fields = ("name", "parent", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Offering only active roots makes the two-level cap a property of
        # the form rather than an error the author runs into. `clean` still
        # enforces it — this is the affordance, not the guarantee.
        parents = AreaModel.objects.filter(is_active=True, parent__isnull=True)
        if self.instance.pk:
            parents = parents.exclude(pk=self.instance.pk)
            self.fields["tenant"].initial = self.instance.tenant
        self.fields["parent"].queryset = parents

    def clean_tenant(self):
        tenant = self.cleaned_data["tenant"]
        if not async_to_sync(TenantLookupRepositoryImpl().tenant_exists)(tenant):
            raise forms.ValidationError(_("No active tenant with that UUID."))
        return tenant

    def clean(self):
        """Re-assert the domain invariants rather than restating them.

        The admin is the only creation path for areas today, so this is
        load-bearing validation, not a convenience. The rules themselves live
        in the domain so a later mutation inherits them.
        """
        cleaned = super().clean()
        parent = cleaned.get("parent")

        try:
            if parent is not None:
                ensure_parent_is_root(AreaEntity.from_model(parent))

                if (
                    self.instance.pk
                    and AreaModel.objects.filter(parent_id=self.instance.pk).exists()
                ):
                    raise InvalidAreaHierarchyError(
                        f"Area {cleaned.get('name')!r} has children and cannot "
                        f"become a child itself"
                    )
        except InvalidAreaHierarchyError as exc:
            raise forms.ValidationError(str(exc)) from exc

        return cleaned


@admin.register(AreaModel)
class AreaAdmin(ActivableAdminMixin, admin.ModelAdmin):
    form = AreaAdminForm
    list_display = ("name", "parent", "level", "tenant", "is_active", "deactivated_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("parent__name", "name")
    readonly_fields = ("id", "deactivated_at", "created_at", "updated_at")

    @admin.display(description=_("Level"))
    def level(self, obj) -> str:
        return _("Root") if obj.parent_id is None else _("Sub-area")

    def save_model(self, request, obj, form, change):
        """`tenant` comes from the form; `tenant_user` records the admin who
        created the area and is never editable — it is authorship, and
        rewriting it on edit would erase who actually added the row."""
        obj.tenant = form.cleaned_data["tenant"]
        if not change:
            obj.tenant_user = request.user.id
        super().save_model(request, obj, form, change)
