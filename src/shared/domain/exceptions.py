class DomainError(Exception):
    """Base for all domain-level errors across bounded contexts."""


class NotFoundError(DomainError):
    """Raised when a lookup for a specific entity/aggregate finds nothing."""


class ApplicationError(DomainError):
    """Errors in the application layer (validation, orchestration, business rules)."""


class InfrastructureError(DomainError):
    """Errors in the infrastructure layer (persistence, repos, external services)."""


class DuplicateOperationError(Exception):
    """Raised by `IdempotencyReservationRepository.reserve_and_run` when
    `operation_id` was already reserved by a prior attempt. Deliberately not
    a `DomainError` subclass: it's a replay signal for the caller to act on
    (return the prior outcome), not a new error to surface as-is. Carries
    the prior attempt's outcome so the caller can decide how to respond —
    see design.md - Decisions (mutation-idempotency-rate-limit)."""

    def __init__(
        self,
        operation_id: str,
        status: str,
        response_payload: dict | None,
    ) -> None:
        super().__init__(f"operation_id already reserved: {operation_id}")
        self.operation_id = operation_id
        self.status = status
        self.response_payload = response_payload
