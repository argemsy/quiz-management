import uuid

import pytest

from src.account.shared.account_event_channels import AccountEventChannel
from src.eventing.infrastructure.persistence.django.models import AuditLog
from src.eventing.shared.eventing_enums import (
    AuditLogActionEnum,
    AuditLogContentTypeEnum,
    AuditLogSourceEnum,
)
from src.shared.infrastructure.event_bus import EventBusMessage, get_event_bus

pytestmark = pytest.mark.django_db


def test_publishing_entity_changed_records_an_audit_log_row():
    """Exercises the real wiring set up in `EventingConfig.ready()` — same
    style as `test_dlq_end_to_end.py` — rather than awaiting the handler
    directly: `publish()` is always called from sync code in production
    (Django admin), which drives the async handler through the bus's own
    `asyncio.run()` fallback, not a bare `await`."""
    object_id = uuid.uuid4()
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    correlation_id = str(uuid.uuid4())

    get_event_bus().publish(
        EventBusMessage(
            channel=AccountEventChannel.ENTITY_CHANGED,
            resource_name="tenant_addition",
            correlation_id=correlation_id,
            data={
                "object_id": object_id,
                "object_repr": "Tenant object",
                "content_type": AuditLogContentTypeEnum.TENANT,
                "source_type": AuditLogSourceEnum.ADMIN,
                "action_type": AuditLogActionEnum.ADDITION,
                "user": user_id,
                "tenant": tenant_id,
                "previous_state": {},
                "current_state": {"name": "Acme"},
            },
        )
    )

    row = AuditLog.objects.get(object_id=object_id)
    assert row.content_type == AuditLogContentTypeEnum.TENANT.value
    assert row.source_type == AuditLogSourceEnum.ADMIN.value
    assert row.action_type == AuditLogActionEnum.ADDITION.value
    assert row.user == user_id
    assert row.tenant == tenant_id
    assert str(row.correlation_id) == correlation_id
    assert row.metadata == {"previous_state": {}, "current_state": {"name": "Acme"}}
