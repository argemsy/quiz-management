from functools import cached_property
from typing import Any

from strawberry.fastapi import BaseContext
from strawberry.types import Info as _Info

from src.shared.presentation.schema.types import UserSession


class Context(BaseContext):
    @cached_property
    def user_session(self) -> UserSession | None:
        if not (req := self.request):
            return None
        return getattr(req.state, "user_session", None)

    @cached_property
    def correlation_id(self) -> str:
        if not (req := self.request):
            raise ValueError("correlation_id requires HTTP request context")
        correlation_id = req.headers.get("X-Correlation-ID")
        if not correlation_id:
            raise ValueError(
                "X-Correlation-ID header is required to trace a mutation "
                "and everything it publishes. Client must generate and send "
                "a unique UUID per request."
            )
        return correlation_id

    @cached_property
    def operation_id(self) -> str:
        """Client-minted idempotency key — one per distinct mutation attempt
        (e.g. per button click), reused across retries of that same attempt
        until a terminal response is seen. Distinct from `correlation_id`
        (tracing); see design.md - Decisions (mutation-idempotency-rate-limit).
        """
        if not (req := self.request):
            raise ValueError("operation_id requires HTTP request context")
        operation_id = req.headers.get("X-Operation-ID")
        if not operation_id:
            raise ValueError(
                "X-Operation-ID header is required for mutation idempotency. "
                "Client must generate and send a unique UUID per mutation "
                "attempt, never server-side."
            )
        return operation_id


async def get_context() -> Context:
    return Context()


# Info = _Info[Context, RootValueType]
Info = _Info[Context, Any]
