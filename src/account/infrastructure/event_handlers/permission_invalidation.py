from src.account.infrastructure.repositories.permission_version_repository_imp import (
    PermissionVersionRepositoryImpl,
)
from src.eventing.shared.eventing_enums import (
    AuditLogActionEnum,
    AuditLogContentTypeEnum,
)
from src.shared.infrastructure.cache import create_redis_client
from src.shared.infrastructure.event_bus import EventBusMessage
from src.shared.infrastructure.logging import get_logger

logger = get_logger(__name__)


async def handle_entity_changed_for_permissions(event: EventBusMessage) -> None:
    """Subscribed to `AccountEventChannel.ENTITY_CHANGED` in
    `AccountConfig.ready()`, alongside `eventing`'s own subscriber to the
    same event for audit logging — this one is unrelated to auditing, it
    only keeps the `UserTenant`-scoped permission-version counter (see
    design.md - Decisions) in sync with membership changes.

    `previous_state`/`current_state` live in `event.data` (round-tripped
    through `_json_safe_state` by `AuditableAdminMixin`, so `role`/
    `is_active` are plain values here, not enum members); `content_type`
    in `event.data` is the raw `AuditLogContentTypeEnum` member, not
    JSON-encoded.

    Bumps on a `role` change, an `is_active` change, or a soft-delete
    (`DELETION`) — not just `role` — since a deactivated or soft-deleted
    membership needs its session invalidated too, not only a role change.

    `MyUser.is_superuser` changes are NOT covered here: `MyUserAdmin`
    doesn't publish this event at all (`account-audit-trail` deliberately
    scoped `USER` out of audit logging), so the user-scoped version is
    bumped directly from `MyUserAdmin.save_model` instead — see
    `src/account/presentation/admin/user.py`.
    """
    data = event.data or {}
    if data.get("content_type") != AuditLogContentTypeEnum.TENANT_USER:
        return

    previous_state = data.get("previous_state") or {}
    current_state = data.get("current_state") or {}
    action_type = data.get("action_type")

    role_changed = previous_state.get("role") != current_state.get("role")
    active_changed = previous_state.get("is_active") != current_state.get("is_active")
    deleted = action_type == AuditLogActionEnum.DELETION

    if not (role_changed or active_changed or deleted):
        return

    user_tenant_id = data.get("object_id")
    if user_tenant_id is None:
        return

    # A fresh client, not the shared singleton: this handler is published
    # from sync Django admin code today, which the event bus dispatches
    # via a fresh `asyncio.run()` per call (no running loop to reuse) — a
    # cached client's connection would be bound to a loop already closed
    # by the time a second admin action runs. See create_redis_client()'s
    # docstring.
    client = create_redis_client()
    try:
        repository = PermissionVersionRepositoryImpl(client)
        new_version = await repository.bump_user_tenant_version(user_tenant_id)
    finally:
        await client.aclose()

    logger.info(
        "permission_version_bumped",
        scope="user_tenant",
        user_tenant_id=str(user_tenant_id),
        role_changed=role_changed,
        active_changed=active_changed,
        deleted=deleted,
        new_version=new_version,
    )
