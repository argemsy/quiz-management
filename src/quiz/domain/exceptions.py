import uuid

from src.shared.domain.exceptions import DomainError, NotFoundError


class TenantNotFoundError(NotFoundError):
    def __init__(self, tenant_id: uuid.UUID) -> None:
        super().__init__(f"Tenant {tenant_id} not found")
        self.tenant_id = tenant_id


class TenantUserNotFoundError(NotFoundError):
    def __init__(self, tenant_id: uuid.UUID, tenant_user_id: uuid.UUID) -> None:
        super().__init__(
            f"TenantUser {tenant_user_id} not found for tenant {tenant_id}"
        )
        self.tenant_id = tenant_id
        self.tenant_user_id = tenant_user_id


class InvalidQuestionError(DomainError):
    """Raised by `QuestionEntity.__post_init__` when a question fails its
    own invariants (e.g. no answer choices) — a `DomainError` subclass so
    `@handle_mutations_exceptions` maps it to `ValidationErrorResponse`,
    not the catch-all `InternalErrorResponse`."""
