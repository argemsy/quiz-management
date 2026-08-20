import asyncio

import pytest
from django.contrib import admin
from django.test import RequestFactory

from src.account.infrastructure.persistence.django.models import MyUser
from src.account.infrastructure.repositories.permission_version_repository_imp import (
    PermissionVersionRepositoryImpl,
)
from src.account.presentation.admin.user import MyUserAdmin
from src.shared.infrastructure.cache import create_redis_client

pytestmark = pytest.mark.django_db


def _silence_messages(model_admin):
    """`message_user` needs `MessageMiddleware` on the request; this test
    calls the admin method directly, so it's stubbed out rather than wired
    up (same as tests/account/presentation/admin/test_audit_trail.py)."""
    model_admin.message_user = lambda request, message, level=None: None
    return model_admin


@pytest.fixture
def admin_request() -> RequestFactory:
    return RequestFactory().post("/admin/")


def _get_user_permission_version(user_id) -> int:
    """A fresh client per call, same reason `save_model` itself uses one
    (see create_redis_client()'s docstring): this is a sync test calling
    `asyncio.run()` more than once, and a shared client's connection would
    be bound to a loop this function already closed on a prior call."""

    async def _read() -> int:
        client = create_redis_client()
        try:
            return await PermissionVersionRepositoryImpl(client).get_user_version(
                user_id
            )
        finally:
            await client.aclose()

    return asyncio.run(_read())


def test_is_superuser_change_bumps_the_user_scoped_permission_version(admin_request):
    user = MyUser.objects.create_user(
        username="bob", email="bob@example.com", password="pw", is_superuser=False
    )
    user_admin = _silence_messages(MyUserAdmin(MyUser, admin.site))
    assert _get_user_permission_version(user.id) == 0

    user.is_superuser = True
    user_admin.save_model(admin_request, user, form=None, change=True)

    assert _get_user_permission_version(user.id) == 1


def test_unrelated_field_change_does_not_bump_the_permission_version(admin_request):
    user = MyUser.objects.create_user(
        username="carol", email="carol@example.com", password="pw", is_superuser=False
    )
    user_admin = _silence_messages(MyUserAdmin(MyUser, admin.site))

    user.first_name = "Carol"
    user_admin.save_model(admin_request, user, form=None, change=True)

    assert _get_user_permission_version(user.id) == 0


def test_creating_a_user_does_not_bump_the_permission_version(admin_request):
    user_admin = _silence_messages(MyUserAdmin(MyUser, admin.site))
    user = MyUser(username="dave", email="dave@example.com", is_superuser=True)
    user.set_password("pw")

    user_admin.save_model(admin_request, user, form=None, change=False)

    assert _get_user_permission_version(user.id) == 0
