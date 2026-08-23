from abc import ABC, abstractmethod
from typing import Callable, TypeVar

from src.shared.domain.enums import EnumChoices

T = TypeVar("T")


class IdempotencyOutcome(EnumChoices):
    """Mirrors `IdempotencyKeyStatus` (owned by `eventing`, the app that
    hosts the `IdempotencyKey` model) without any consumer app importing
    that enum directly — same reasoning as the port itself living here
    instead of in `eventing`: this is cross-cutting infra with no single
    domain owner, not a dependency between two bounded contexts."""

    IN_PROGRESS = "IN_PROGRESS"
    SUCCEEDED = "SUCCEEDED"
    FAILED_TERMINAL = "FAILED_TERMINAL"


class IdempotencyReservationRepository(ABC):
    """Port for atomically reserving a mutation's idempotency key alongside
    its business write, so a database-level uniqueness guarantee — not a
    cache lock — is what actually prevents a duplicate record. Consumers
    (e.g. `quiz`'s `CreateQuizUseCase`) never import `eventing`'s
    `IdempotencyKey` model directly; only this port's implementation does.
    See design.md - Decisions (mutation-idempotency-rate-limit)."""

    @abstractmethod
    async def reserve_and_run(self, operation_id: str, write: Callable[[], T]) -> T:
        """Atomically reserves `operation_id` and calls `write()` in the
        same database transaction. `write` MUST be a plain synchronous
        callable (no further awaits) so it can run inside the same
        transaction as the reservation.

        Raises `DuplicateOperationError` — carrying the prior attempt's
        status and cached response — if `operation_id` was already
        reserved, without calling `write`.
        """

    @abstractmethod
    async def mark_terminal(
        self, operation_id: str, status: IdempotencyOutcome, response_payload: dict
    ) -> None:
        """Records a mutation attempt's definitive outcome (success or a
        business/validation error) so a later duplicate `operation_id` can
        be replayed instead of re-executed."""

    @abstractmethod
    async def release(self, operation_id: str) -> None:
        """Drops the reservation after an unexpected internal error (not a
        business/validation error), so a retry with the same `operation_id`
        can attempt the write again instead of being treated as a
        duplicate — see the three-way caching policy in design.md."""
