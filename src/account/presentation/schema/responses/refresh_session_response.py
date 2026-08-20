from typing import Annotated, Optional, Union

import strawberry

from src.shared.presentation.schema.responses import (
    IntegrityErrorResponse,
    InternalErrorResponse,
    ValidationErrorResponse,
)


@strawberry.type(name="RefreshSessionSuccess")
class RefreshSessionPayload:
    operation_id: str
    token: str
    is_staff: bool
    active_tenant_id: Optional[str] = None
    role: Optional[str] = None


RefreshSessionResponse = Annotated[
    Union[
        ValidationErrorResponse,
        IntegrityErrorResponse,
        InternalErrorResponse,
        RefreshSessionPayload,
    ],
    strawberry.union("RefreshSessionResponse"),
]
