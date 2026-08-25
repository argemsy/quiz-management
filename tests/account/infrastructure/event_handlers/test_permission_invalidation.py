import uuid

import pytest

from src.account.infrastructure.event_handlers.permission_invalidation import (
    handle_entity_changed_for_permissions,
)
from src.account.infrastructure.repositories.permission_version_repository_imp import (
    PermissionVersionRepositoryImpl,
)
from src.account.shared.account_event_channels import AccountEventChannel
from src.eventing.shared.eventing_enums import (
    AuditLogActionEnum,
    AuditLogContentTypeEnum,
)
from src.shared.infrastructure.event_bus import EventBusMessage


@pytest.fixture
def permission_version_repository(redis_client):
    return PermissionVersionRepositoryImpl(redis_client)


def _entity_changed_event(
    *,
    content_type,
    action_type,
    object_id,
    previous_state,
    current_state,
) -> EventBusMessage:
    return EventBusMessage(
        channel=AccountEventChannel.ENTITY_CHANGED,
        resource_name="test_event",
        data={
            "object_id": object_id,
            "object_repr": "test",
            "content_type": content_type,
            "action_type": action_type,
            "user": None,
            "tenant": object_id,
            "previous_state": previous_state,
            "current_state": current_state,
        },
    )


@pytest.mark.asyncio
async def test_role_change_bumps_only_the_user_tenant_key(
    permission_version_repository,
):
    user_tenant_id = uuid.uuid4()
    event = _entity_changed_event(
        content_type=AuditLogContentTypeEnum.TENANT_USER,
        action_type=AuditLogActionEnum.CHANGE,
        object_id=user_tenant_id,
        previous_state={"role": "COLLABORATOR"},
        current_state={"role": "ADMIN"},
    )

    await handle_entity_changed_for_permissions(event)

    assert (
        await permission_version_repository.get_user_tenant_version(user_tenant_id) == 1
    )


@pytest.mark.asyncio
async def test_unrelated_field_change_does_not_bump(permission_version_repository):
    user_tenant_id = uuid.uuid4()
    event = _entity_changed_event(
        content_type=AuditLogContentTypeEnum.TENANT_USER,
        action_type=AuditLogActionEnum.CHANGE,
        object_id=user_tenant_id,
        previous_state={"role": "ADMIN", "is_active": True},
        current_state={"role": "ADMIN", "is_active": True},
    )

    await handle_entity_changed_for_permissions(event)

    assert (
        await permission_version_repository.get_user_tenant_version(user_tenant_id) == 0
    )


@pytest.mark.asyncio
async def test_non_tenant_user_content_type_is_ignored(
    permission_version_repository,
):
    object_id = uuid.uuid4()
    event = _entity_changed_event(
        content_type=AuditLogContentTypeEnum.TENANT,
        action_type=AuditLogActionEnum.CHANGE,
        object_id=object_id,
        previous_state={"name": "Acme"},
        current_state={"name": "Acme Corp"},
    )

    await handle_entity_changed_for_permissions(event)

    assert await permission_version_repository.get_user_tenant_version(object_id) == 0


@pytest.mark.asyncio
async def test_soft_delete_bumps_even_without_a_role_change(
    permission_version_repository,
):
    user_tenant_id = uuid.uuid4()
    event = _entity_changed_event(
        content_type=AuditLogContentTypeEnum.TENANT_USER,
        action_type=AuditLogActionEnum.DELETION,
        object_id=user_tenant_id,
        previous_state={"role": "ADMIN", "is_active": True},
        current_state={"role": "ADMIN", "is_active": True, "is_deleted": True},
    )

    await handle_entity_changed_for_permissions(event)

    assert (
        await permission_version_repository.get_user_tenant_version(user_tenant_id) == 1
    )
