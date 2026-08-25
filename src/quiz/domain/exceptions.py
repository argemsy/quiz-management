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


class InvalidQuizConfigurationError(DomainError):
    """Raised by `QuizConfiguration.__post_init__` when the configuration
    contradicts itself (e.g. a minimum above the maximum). A `DomainError`
    for the same reason as `InvalidQuestionError`: the client sent bad
    input, so it belongs in `ValidationErrorResponse`, not in the catch-all
    `InternalErrorResponse`."""


class InvalidAreaHierarchyError(DomainError):
    """Raised when an area's placement would break the two-level cap — the
    invariant that keeps cycles unrepresentable. A `DomainError` so a future
    mutation maps it to `ValidationErrorResponse`."""


class DuplicateAreaError(DomainError):
    def __init__(self, name: str, parent_name: str | None) -> None:
        location = f"under {parent_name!r}" if parent_name else "at the root"
        super().__init__(f"An active area named {name!r} already exists {location}")
        self.name = name
        self.parent_name = parent_name


class QuestionLimitExceededError(DomainError):
    def __init__(self, submitted: int, allowed: int) -> None:
        super().__init__(
            f"Quiz accepts at most {allowed} questions, {submitted} submitted"
        )
        self.submitted = submitted
        self.allowed = allowed


class AnswerChoiceLimitExceededError(DomainError):
    def __init__(self, question_text: str, submitted: int, allowed: int) -> None:
        super().__init__(
            f"Question {question_text!r} accepts at most {allowed} answer "
            f"choices, {submitted} submitted"
        )
        self.question_text = question_text
        self.submitted = submitted
        self.allowed = allowed
