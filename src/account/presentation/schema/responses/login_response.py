from typing import Annotated, Optional, Union

import strawberry

from src.shared.presentation.schema.responses import (
    IntegrityErrorResponse,
    InternalErrorResponse,
    ValidationErrorResponse,
)


@strawberry.type(name="LoginSuccess")
class LoginPayload:
    operation_id: str
    token: str
    is_staff: bool
    active_tenant_id: Optional[str] = None
    role: Optional[str] = None


LoginResponse = Annotated[
    Union[
        ValidationErrorResponse,
        IntegrityErrorResponse,
        InternalErrorResponse,
        LoginPayload,
    ],
    strawberry.union("LoginResponse"),
]
