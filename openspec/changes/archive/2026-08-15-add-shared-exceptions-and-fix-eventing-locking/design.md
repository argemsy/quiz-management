## Context

See proposal.md for motivation. Current state:

- `FailedEventMessageRepositoryImpl.mark_resolved`/`mark_retry_failed` use `FailedEventMessage.objects.get(id=id)` → mutate attributes → `.save(update_fields=[...])`. No transaction, no lock — a textbook lost-update race between two concurrent calls for the same `id`.
- `RetryFailedEventUseCase.execute` raises a bare `LookupError` when `repository.get_by_id` returns `None`. No project-wide domain exception vocabulary exists yet — this is the first bounded context to need one.
- `FailedEventMessage` already has a `status` field (`FailedEventStatus`: `PENDING`/`RESOLVED`/`ABANDONED`) that fully captures its lifecycle — it does not need (and, per explicit decision, will not get) `is_active`/`is_deleted` soft-delete semantics; those model a different concern (a record being logically removed from view) that doesn't apply to a dead-letter record's retry lifecycle.

## Goals / Non-Goals

**Goals:**
- Eliminate the read-modify-write race in `mark_resolved`/`mark_retry_failed`.
- Give `eventing` (and future bounded contexts) a minimal, reusable domain exception base in `shared/`.
- Replace the ad hoc `LookupError` with a proper domain exception.

**Non-Goals:**
- No model/schema changes to `FailedEventMessage` — `status` is the correct and sufficient state discriminator for this model.
- No changes to `get_by_id` — it stays a plain, unfiltered lookup; only the two *mutating* methods need the concurrency guard, since they're the ones doing read-then-write.
- No `async_database()` decorator work — separate change.
- No attempt to prevent a handler from being *invoked* twice by two racing retries (the race window between `RetryFailedEventUseCase.execute`'s initial `get_by_id` and its later `mark_resolved`/`mark_retry_failed` call). This change fixes the database write race; closing the handler-invocation race would require locking before invoking the handler, which changes retry semantics more invasively and isn't what was asked for here.

## Decisions

**1. Guard the mutation with `status=PENDING` in the `SELECT`, not just an `id` match.**
```python
from django.db import transaction

def mark_resolved(self, id: uuid.UUID) -> FailedEventMessageEntity:
    with transaction.atomic():
        model = (
            FailedEventMessage.objects.select_for_update()
            .filter(id=id, status=FailedEventStatus.PENDING.value)
            .first()
        )
        if model is None:
            raise FailedEventMessageNotFoundError(id)
        model.status = FailedEventStatus.RESOLVED.value
        model.retry_count += 1
        model.save(update_fields=["status", "retry_count", "updated_at"])
        return self._to_entity(model)
```
(`mark_retry_failed` follows the same shape.) Filtering by `status=PENDING` does double duty: it's the lock target for `select_for_update()`, and it's the business invariant ("you can only resolve/fail-retry a row that's still pending"). If a second concurrent call reaches this `SELECT` after the first committed, it simply finds no matching row (status is no longer `PENDING`) and raises — instead of silently re-applying a state transition that already happened. Alternative considered: lock by `id` alone (no status filter), let the second caller just re-write the same terminal state. Rejected — it hides a real conflict (two processes both believe they resolved this event) behind a successful-looking return.

**2. `get_by_id` stays exception-free and unfiltered.**
It's a query, not a command — returning `Optional[FailedEventMessageEntity]` and letting the *caller* decide what "not found" means is the existing, correct contract (`RetryFailedEventUseCase` already does this). No change needed there beyond swapping the exception type raised on `None`.

**3. Minimal exception hierarchy: `DomainError` → `NotFoundError`, nothing else yet.**
```python
# src/shared/domain/exceptions.py
class DomainError(Exception):
    """Base for all domain-level errors across bounded contexts."""


class NotFoundError(DomainError):
    """Raised when a lookup for a specific entity/aggregate finds nothing."""
```
```python
# src/eventing/domain/exceptions.py
class FailedEventMessageNotFoundError(NotFoundError):
    def __init__(self, id: uuid.UUID):
        super().__init__(f"FailedEventMessage {id} not found")
        self.id = id
```
No `ConflictError` or other subclasses yet — nothing in this change needs to raise one (a `status`-guarded miss is modeled as "not found in a retriable state", which `NotFoundError` already covers honestly). Adding exception types with no caller would be speculative; the next bounded context that needs a different category can add it to `shared/domain/exceptions.py` when it has an actual use.

**4. `FakeFailedEventMessageRepository` (test double) mirrors the same contract.**
Its `mark_resolved`/`mark_retry_failed` gain the same "only if currently PENDING, else raise `FailedEventMessageNotFoundError`" check, so unit tests against the fake actually exercise the guard, not just the real DB-backed implementation.

## Risks / Trade-offs

- **[Risk]** `select_for_update()` is a no-op on SQLite (this project's dev/test database) — Django doesn't add a `FOR UPDATE` clause and provides no real row-level lock there. → **Mitigation**: the `status=PENDING` filter is the actual correctness fix and works identically regardless of backend; `select_for_update()` becomes fully effective the moment the project moves to a backend that supports it (Postgres), with zero code changes needed then. Tests verify the filter logic (call `mark_resolved` twice, assert the second raises), not real concurrent locking — genuine multi-threaded locking isn't practically testable against SQLite anyway.
- **[Risk]** Widening what counts as "not found" (id missing, or id present but not `PENDING`) into one exception type could be confusing if a caller ever needs to distinguish the two. → **Mitigation**: no current caller needs that distinction (the admin's retry action just increments a failed-counter either way); if one shows up, `FailedEventMessageNotFoundError` can carry more detail or a sibling exception can be added then.

## Migration Plan

No data migration. Deployment is a plain code change:
1. Add `shared/domain/exceptions.py` and `eventing/domain/exceptions.py`.
2. Update the repository implementation and the retry use case to use them.
3. Update the fake repository and tests.
4. `manage.py check` + `make test`.

Rollback is a plain revert.
