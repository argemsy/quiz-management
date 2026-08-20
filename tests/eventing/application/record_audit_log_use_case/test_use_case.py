import uuid

import pytest

from src.eventing.application.record_audit_log_use_case.dto import RecordAuditLogDTO
from src.eventing.application.record_audit_log_use_case.use_case import (
    RecordAuditLogUseCase,
)
from src.eventing.shared.eventing_enums import (
    AuditLogActionEnum,
    AuditLogContentTypeEnum,
    AuditLogSourceEnum,
)
from tests.fixtures.eventing_fixtures import FakeAuditLogRepository


@pytest.mark.asyncio
async def test_execute_records_an_entity_matching_the_dto(fake_audit_log_repository):
    use_case = RecordAuditLogUseCase(fake_audit_log_repository)
    object_id = uuid.uuid4()
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    dto = RecordAuditLogDTO(
        object_id=object_id,
        content_type=AuditLogContentTypeEnum.TENANT,
        source_type=AuditLogSourceEnum.ADMIN,
        action_type=AuditLogActionEnum.ADDITION,
        object_repr="Tenant object",
        user=user_id,
        tenant=tenant_id,
        previous_state={},
        current_state={"name": "Acme"},
    )

    recorded = await use_case.execute(dto)

    assert recorded.object_id == object_id
    assert recorded.content_type == AuditLogContentTypeEnum.TENANT
    assert recorded.source_type == AuditLogSourceEnum.ADMIN
    assert recorded.action_type == AuditLogActionEnum.ADDITION
    assert recorded.user == user_id
    assert recorded.tenant == tenant_id
    assert recorded.metadata == {
        "previous_state": {},
        "current_state": {"name": "Acme"},
    }
    assert isinstance(fake_audit_log_repository, FakeAuditLogRepository)
    assert fake_audit_log_repository.recorded == [recorded]
