from typing import Callable, TypeVar

from django.db import IntegrityError, transaction

from src.eventing.infrastructure.persistence.django.models import IdempotencyKey
from src.eventing.shared.eventing_enums import IdempotencyKeyStatus
from src.shared.domain.exceptions import DuplicateOperationError
from src.shared.domain.repositories.idempotency_reservation_repository import (
    IdempotencyOutcome,
    IdempotencyReservationRepository,
)
from src.shared.infrastructure.persistence.django.models import async_database

T = TypeVar("T")


class IdempotencyReservationRepositoryImpl(IdempotencyReservationRepository):
    @async_database()
    def reserve_and_run(self, operation_id: str, write: Callable[[], T]) -> T:
        try:
            with transaction.atomic():
                IdempotencyKey.objects.create(operation_id=operation_id)
                return write()
        except IntegrityError as exc:
            existing = IdempotencyKey.objects.filter(operation_id=operation_id).first()
            raise DuplicateOperationError(
                operation_id=operation_id,
                status=(
                    IdempotencyOutcome(existing.status).value
                    if existing
                    else IdempotencyOutcome.IN_PROGRESS.value
                ),
                response_payload=existing.response_payload if existing else None,
            ) from exc

    @async_database()
    def mark_terminal(
        self, operation_id: str, status: IdempotencyOutcome, response_payload: dict
    ) -> None:
        IdempotencyKey.objects.filter(operation_id=operation_id).update(
            status=IdempotencyKeyStatus(status.value).value,
            response_payload=response_payload,
        )

    @async_database()
    def release(self, operation_id: str) -> None:
        IdempotencyKey.objects.filter(operation_id=operation_id).delete()
