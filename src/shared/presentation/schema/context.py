from functools import cached_property
from typing import Any

import strawberry
from strawberry.fastapi import BaseContext
from strawberry.types import Info as _Info

from shared.presentation.schema.responses import get_operation_id
from src.shared.presentation.schema.auth import authorize
from src.shared.presentation.schema.types import UserSession


class Context(BaseContext):
    @cached_property
    def user_session(self) -> UserSession | None:
        if not (req := self.request):
            return None

        if not (authorization := req.headers.get("Authorization", None)):
            return None
        return authorize(authorization)

    @cached_property
    def operation_id(self) -> str:
        if not (req := self.request):
            raise ValueError("operation_id requires HTTP request context")
        operation_id = req.headers.get("X-Operation-ID")
        if not operation_id:
            raise ValueError(
                "X-Operation-ID header is required for mutation idempotency. "
                "Client must generate and send a unique UUID per request."
            )
        return operation_id


async def get_context() -> Context:
    return Context()


# Info = _Info[Context, RootValueType]
Info = _Info[Context, Any]
