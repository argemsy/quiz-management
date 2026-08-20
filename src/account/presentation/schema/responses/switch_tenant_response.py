from typing import Annotated, Optional, Union

import strawberry

from src.shared.presentation.schema.responses import (
    IntegrityErrorResponse,
    InternalErrorResponse,
    ValidationErrorResponse,
)


@strawberry.type(name="SwitchTenantSuccess")
class SwitchTenantPayload:
    operation_id: str
    token: str
    active_tenant_id: Optional[str] = None
    role: Optional[str] = None


SwitchTenantResponse = Annotated[
    Union[
        ValidationErrorResponse,
        IntegrityErrorResponse,
        InternalErrorResponse,
        SwitchTenantPayload,
    ],
    strawberry.union("SwitchTenantResponse"),
]
