from typing import Callable, TypeVar

from src.shared.domain.repositories.idempotency_reservation_repository import (
    IdempotencyOutcome,
    IdempotencyReservationRepository,
)

T = TypeVar("T")


class IdempotencyService:
    """Wraps `IdempotencyReservationRepository` so use cases depend on a
    service, never a repository directly (see CLAUDE.md mandatory pattern:
    use cases receive only services). Generic across any use case's
    idempotency-protected write — not entity-specific."""

    def __init__(self, repository: IdempotencyReservationRepository) -> None:
        self.repository = repository

    async def run(self, operation_id: str, write: Callable[[], T]) -> T:
        """Reserves `operation_id` and runs `write()` atomically. Raises
        `DuplicateOperationError` if already reserved — never returns a
        sentinel on failure, so a caller with no try/except still can't
        reach code after this call unless it actually succeeded."""
        return await self.repository.reserve_and_run(operation_id, write)

    async def mark_success(self, operation_id: str, response_payload: dict) -> None:
        await self.repository.mark_terminal(
            operation_id, IdempotencyOutcome.SUCCEEDED, response_payload
        )
