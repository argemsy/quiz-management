from pydantic import BaseModel, ConfigDict


class CorrelationIdDTO(BaseModel):
    """Mixin for use case DTOs that need to propagate tracing correlation —
    e.g. into an `EventBusMessage` or a success/failure log line. Segregated
    from `OperationIdDTO`: a DTO inherits only the mixin(s) it actually
    needs, never both by default."""

    model_config = ConfigDict(frozen=True)

    correlation_id: str


class OperationIdDTO(BaseModel):
    """Mixin for use case DTOs that need the client-minted idempotency key
    (see `IdempotencyService`). Segregated from `CorrelationIdDTO` — most
    use cases have no idempotency-protected write and shouldn't carry this
    field."""

    model_config = ConfigDict(frozen=True)

    operation_id: str
