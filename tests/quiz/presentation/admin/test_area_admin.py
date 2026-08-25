import uuid

import pytest
from django.contrib import admin
from django.test import RequestFactory

from src.account.infrastructure.persistence.django.models import (
    MyUser,
    TenantModel,
    UserTenantModel,
)
from src.account.shared.account_enums import TenantTypeEnum, UserTenantRoleEnum
from src.quiz.infrastructure.persistence.django.models import AreaModel
from src.quiz.presentation.admin.area import AreaAdmin, AreaAdminForm

pytestmark = pytest.mark.django_db


@pytest.fixture
def tenant() -> TenantModel:
    return TenantModel.objects.create(
        tenant_type=TenantTypeEnum.COMPANY.value,
        name="Colegio San José",
        slug="colegio-san-jose",
    )


@pytest.fixture
def admin_request(tenant):
    user = MyUser.objects.create_superuser(
        username="admin", email="admin@example.com", password="pw"
    )
    UserTenantModel.objects.create(
        user=user,
        tenant=tenant,
        role=UserTenantRoleEnum.ADMIN.value,
        is_active=True,
    )
    request = RequestFactory().post("/admin/")
    request.user = user
    return request


def _area_admin() -> AreaAdmin:
    model_admin = AreaAdmin(AreaModel, admin.site)
    # `message_user` needs MessageMiddleware; these call the actions directly.
    model_admin.message_user = lambda request, message, level=None: None
    return model_admin


def test_an_area_can_actually_be_created_through_the_admin(admin_request, tenant):
    """The reason `tenant` is reintroduced on the form at all.

    `AreaModel.tenant` is `editable=False` and NOT NULL, so a plain ModelForm
    omits it and the save fails the constraint. Areas have no mutation, so
    that would leave them impossible to create anywhere.
    """
    model_admin = _area_admin()
    form = AreaAdminForm(
        data={
            "name": "Ciencias",
            "parent": "",
            "is_active": True,
            "tenant": str(tenant.id),
        }
    )

    assert form.is_valid(), form.errors
    area = form.save(commit=False)
    model_admin.save_model(admin_request, area, form, change=False)

    stored = AreaModel.objects.get(name="Ciencias")
    assert stored.tenant == tenant.id
    assert stored.tenant_user == admin_request.user.id


def test_authorship_is_not_rewritten_on_edit(admin_request, tenant, make_area):
    original_author = uuid.uuid4()
    area = make_area(name="Ciencias", tenant=tenant.id, tenant_user=original_author)

    form = AreaAdminForm(
        data={
            "name": "Ciencias Naturales",
            "parent": "",
            "is_active": True,
            "tenant": str(tenant.id),
        },
        instance=area,
    )
    assert form.is_valid(), form.errors
    _area_admin().save_model(admin_request, form.save(commit=False), form, change=True)

    area.refresh_from_db()
    assert area.name == "Ciencias Naturales"
    assert area.tenant_user == original_author


def test_form_rejects_an_unknown_tenant():
    form = AreaAdminForm(
        data={
            "name": "Ciencias",
            "parent": "",
            "is_active": True,
            "tenant": str(uuid.uuid4()),
        }
    )

    assert not form.is_valid()
    assert "No active tenant" in str(form.errors)


def test_deactivate_action_stamps_the_timestamp(admin_request, make_area):
    area = make_area(name="Ciencias")

    _area_admin().deactivate_instances(
        admin_request, AreaModel.objects.filter(pk=area.pk)
    )

    area.refresh_from_db()
    assert not area.is_active
    assert area.deactivated_at is not None


def test_activate_action_clears_the_timestamp(admin_request, make_area):
    area = make_area(name="Ciencias")
    model_admin = _area_admin()
    queryset = AreaModel.objects.filter(pk=area.pk)

    model_admin.deactivate_instances(admin_request, queryset)
    model_admin.activate_instances(admin_request, queryset)

    area.refresh_from_db()
    assert area.is_active
    assert area.deactivated_at is None


def test_parent_choices_offer_only_active_roots(make_area):
    root = make_area(name="Ciencias")
    child = make_area(name="Ciencias I", parent=root)
    inactive = make_area(
        name="Historia", tenant=root.tenant, tenant_user=root.tenant_user
    )
    inactive.is_active = False
    inactive.save(update_fields=["is_active"])

    choices = set(AreaAdminForm().fields["parent"].queryset)

    assert root in choices
    assert child not in choices
    assert inactive not in choices


def test_an_area_is_not_offered_as_its_own_parent(make_area):
    root = make_area(name="Ciencias")

    assert root not in set(AreaAdminForm(instance=root).fields["parent"].queryset)


def test_form_rejects_a_third_level(tenant, make_area):
    """The parent queryset already hides children, so this covers the value
    arriving anyway — a stale page, or a direct POST."""
    root = make_area(name="Ciencias", tenant=tenant.id)
    child = make_area(name="Ciencias I", parent=root)

    form = AreaAdminForm(
        data={
            "name": "Ciencias I-A",
            "parent": str(child.pk),
            "is_active": True,
            "tenant": str(tenant.id),
        }
    )
    form.fields["parent"].queryset = AreaModel.objects.all()

    assert not form.is_valid()
    assert "already a child" in str(form.errors)


def test_form_rejects_giving_a_parent_to_an_area_with_children(tenant, make_area):
    root = make_area(name="Ciencias", tenant=tenant.id)
    make_area(name="Ciencias I", parent=root)
    other_root = make_area(
        name="Matemática", tenant=root.tenant, tenant_user=root.tenant_user
    )

    form = AreaAdminForm(
        data={
            "name": "Ciencias",
            "parent": str(other_root.pk),
            "is_active": True,
            "tenant": str(tenant.id),
        },
        instance=root,
    )

    assert not form.is_valid()
    assert "has children" in str(form.errors)


def test_form_accepts_a_valid_child(tenant, make_area):
    root = make_area(name="Ciencias", tenant=tenant.id)

    form = AreaAdminForm(
        data={
            "name": "Ciencias I",
            "parent": str(root.pk),
            "is_active": True,
            "tenant": str(tenant.id),
        }
    )

    assert form.is_valid(), form.errors
