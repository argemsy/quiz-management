class DomainError(Exception):
    """Base for all domain-level errors across bounded contexts."""


class NotFoundError(DomainError):
    """Raised when a lookup for a specific entity/aggregate finds nothing."""


class ApplicationError(DomainError):
    """Errors in the application layer (validation, orchestration, business rules)."""


class InfrastructureError(DomainError):
    """Errors in the infrastructure layer (persistence, repos, external services)."""
