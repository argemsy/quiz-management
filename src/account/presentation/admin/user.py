import asyncio

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from src.account.infrastructure.persistence.django.models import MyUser
from src.account.infrastructure.repositories.permission_version_repository_imp import (
    PermissionVersionRepositoryImpl,
)
from src.shared.infrastructure.cache import create_redis_client
from src.shared.presentation.admin import ActivableAdminMixin


@admin.register(MyUser)
class MyUserAdmin(ActivableAdminMixin, UserAdmin):
    """`is_superuser` changes bump the user's permission-version counter
    directly (see design.md - Decisions) rather than going through
    `AuditableAdminMixin`/`AccountEventChannel.ENTITY_CHANGED`: that event
    is consumed by `eventing` to write an `AuditLog` row, and
    `account-audit-trail` deliberately scoped `MyUser` out of audit
    logging (only `TENANT`/`TENANT_USER` are wired there). Publishing
    `ENTITY_CHANGED` here to piggyback on it for invalidation would
    silently start auditing `MyUser` too — an unintended scope expansion
    of that other change. This bump is unrelated to auditing, so it
    bypasses that event entirely."""

    ordering = ("email",)
    list_display = ("email", "username", "is_staff", "is_active")
    search_fields = ("email", "username")
    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "username", "password1", "password2"),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        previous_is_superuser = None
        if change:
            previous_is_superuser = (
                MyUser.objects.filter(pk=obj.pk)
                .values_list("is_superuser", flat=True)
                .first()
            )

        super().save_model(request, obj, form, change)

        if (
            change
            and previous_is_superuser is not None
            and previous_is_superuser != obj.is_superuser
        ):
            asyncio.run(_bump_user_permission_version(obj.pk))


async def _bump_user_permission_version(user_id) -> None:
    """A fresh client, not the shared singleton: `save_model` runs sync
    (Django admin has no running event loop), so each call wraps its own
    `asyncio.run()` — a cached client's connection would be bound to a
    loop already closed by the time a second admin request runs. See
    `create_redis_client()`'s docstring."""
    client = create_redis_client()
    try:
        await PermissionVersionRepositoryImpl(client).bump_user_version(user_id)
    finally:
        await client.aclose()
