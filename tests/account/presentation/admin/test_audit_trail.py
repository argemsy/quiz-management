import pytest
from django.contrib import admin
from django.test import RequestFactory

from src.account.infrastructure.persistence.django.models import (
    MyUser,
    TenantModel,
    UserTenantModel,
)
from src.account.presentation.admin.tenant import TenantAdmin
from src.account.presentation.admin.user_tenant import UserTenantAdmin
from src.account.shared.account_enums import TenantTypeEnum, UserTenantRoleEnum
from src.eventing.infrastructure.persistence.django.models import AuditLog
from src.eventing.shared.eventing_enums import (
    AuditLogActionEnum,
    AuditLogContentTypeEnum,
    AuditLogSourceEnum,
)

pytestmark = pytest.mark.django_db


def _silence_messages(model_admin):
    """`message_user` needs `MessageMiddleware` on the request; these tests
    call admin methods directly, so it's stubbed out rather than wired up."""
    model_admin.message_user = lambda request, message, level=None: None
    return model_admin


@pytest.fixture
def admin_user() -> MyUser:
    return MyUser.objects.create_superuser(
        username="admin", email="admin@example.com", password="pw"
    )


@pytest.fixture
def admin_request(admin_user: MyUser):
    request = RequestFactory().post("/admin/")
    request.user = admin_user
    return request


def test_tenant_add_edit_soft_delete_are_audited(admin_request):
    tenant_admin = _silence_messages(TenantAdmin(TenantModel, admin.site))

    tenant = TenantModel(tenant_type=TenantTypeEnum.COMPANY.value, name="Acme Inc")
    tenant_admin.save_model(admin_request, tenant, form=None, change=False)

    addition = AuditLog.objects.get(
        object_id=tenant.id, action_type=AuditLogActionEnum.ADDITION.value
    )
    assert addition.content_type == AuditLogContentTypeEnum.TENANT.value
    assert addition.source_type == AuditLogSourceEnum.ADMIN.value
    assert addition.user == admin_request.user.id
    assert addition.tenant == tenant.id
    assert addition.metadata["previous_state"] == {}
    assert addition.metadata["current_state"]["name"] == "Acme Inc"

    tenant.name = "Acme Renamed"
    tenant_admin.save_model(admin_request, tenant, form=None, change=True)

    change = AuditLog.objects.get(
        object_id=tenant.id, action_type=AuditLogActionEnum.CHANGE.value
    )
    assert change.metadata["previous_state"]["name"] == "Acme Inc"
    assert change.metadata["current_state"]["name"] == "Acme Renamed"

    queryset = TenantModel.objects.filter(id=tenant.id)
    tenant_admin.soft_delete_instances(admin_request, queryset)

    deletion = AuditLog.objects.get(
        object_id=tenant.id, action_type=AuditLogActionEnum.DELETION.value
    )
    assert deletion.metadata["current_state"]["is_deleted"] is True
    tenant.refresh_from_db()
    assert tenant.is_deleted is True


def test_user_tenant_add_edit_soft_delete_are_audited(admin_request):
    tenant = TenantModel.objects.create(
        tenant_type=TenantTypeEnum.COMPANY.value, name="Beta Co"
    )
    member = MyUser.objects.create_user(
        username="member", email="member@example.com", password="pw"
    )
    user_tenant_admin = _silence_messages(UserTenantAdmin(UserTenantModel, admin.site))

    user_tenant = UserTenantModel(
        user=member, tenant=tenant, role=UserTenantRoleEnum.COLLABORATOR.value
    )
    user_tenant_admin.save_model(admin_request, user_tenant, form=None, change=False)

    addition = AuditLog.objects.get(
        object_id=user_tenant.id, action_type=AuditLogActionEnum.ADDITION.value
    )
    assert addition.content_type == AuditLogContentTypeEnum.TENANT_USER.value
    assert addition.tenant == tenant.id

    user_tenant.role = UserTenantRoleEnum.ADMIN.value
    user_tenant_admin.save_model(admin_request, user_tenant, form=None, change=True)

    change = AuditLog.objects.get(
        object_id=user_tenant.id, action_type=AuditLogActionEnum.CHANGE.value
    )
    assert (
        change.metadata["previous_state"]["role"]
        == UserTenantRoleEnum.COLLABORATOR.value
    )
    assert change.metadata["current_state"]["role"] == UserTenantRoleEnum.ADMIN.value

    queryset = UserTenantModel.objects.filter(id=user_tenant.id)
    user_tenant_admin.soft_delete_instances(admin_request, queryset)

    deletion = AuditLog.objects.get(
        object_id=user_tenant.id, action_type=AuditLogActionEnum.DELETION.value
    )
    assert deletion.tenant == tenant.id


def test_tenant_activate_deactivate_restore_are_audited(admin_request):
    """Regression test for a gap found while reviewing this change: the bulk
    actions from `CommonAdminActionsMixin` other than soft-delete
    (activate/deactivate/restore) used to fall through to the unaudited
    plain `queryset.update(...)` implementations."""
    tenant = TenantModel.objects.create(
        tenant_type=TenantTypeEnum.COMPANY.value, name="Gamma LLC"
    )
    tenant_admin = _silence_messages(TenantAdmin(TenantModel, admin.site))
    queryset = TenantModel.objects.filter(id=tenant.id)

    tenant_admin.deactivate_instances(admin_request, queryset)
    deactivation = AuditLog.objects.get(
        object_id=tenant.id,
        action_type=AuditLogActionEnum.CHANGE.value,
        metadata__current_state__is_active=False,
    )
    assert deactivation.metadata["previous_state"]["is_active"] is True
    assert deactivation.metadata["current_state"]["is_active"] is False

    tenant_admin.activate_instances(admin_request, queryset)
    activation = AuditLog.objects.get(
        object_id=tenant.id,
        action_type=AuditLogActionEnum.CHANGE.value,
        metadata__current_state__is_active=True,
    )
    assert activation.metadata["previous_state"]["is_active"] is False

    tenant_admin.soft_delete_instances(admin_request, queryset)
    tenant_admin.restore_instances(admin_request, queryset)
    restoration = AuditLog.objects.get(
        object_id=tenant.id,
        action_type=AuditLogActionEnum.CHANGE.value,
        metadata__previous_state__is_deleted=True,
        metadata__current_state__is_deleted=False,
    )
    assert restoration.metadata["previous_state"]["is_deleted"] is True
    assert restoration.metadata["current_state"]["is_deleted"] is False
    tenant.refresh_from_db()
    assert tenant.is_deleted is False
