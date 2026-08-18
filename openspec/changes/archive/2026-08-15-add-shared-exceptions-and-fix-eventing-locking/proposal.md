## Why

`FailedEventMessageRepositoryImpl.mark_resolved`/`mark_retry_failed` do a plain `objects.get(id=id)` read, mutate in Python, then `.save(update_fields=[...])` — a classic read-modify-write race. Two concurrent retries of the same dead-letter row (two admin tabs, an automated retry overlapping a manual one) can lose an update or have a `PENDING` write silently overwrite a `RESOLVED` one. Separately, `RetryFailedEventUseCase` raises a bare built-in `LookupError` when a row isn't found — there's no project-wide domain exception vocabulary yet for any bounded context to build on.

## What Changes

- Add `src/shared/domain/exceptions.py`: a minimal base exception hierarchy (`DomainError`, `NotFoundError`) that any bounded context can extend for its own domain errors.
- Add `src/eventing/domain/exceptions.py`: `FailedEventMessageNotFoundError(NotFoundError)`.
- `FailedEventMessageRepositoryImpl.mark_resolved`/`mark_retry_failed`: wrap the fetch in `transaction.atomic()` + `select_for_update()`, filtered by `status=PENDING`. A miss (row doesn't exist, or is no longer `PENDING` because another process already resolved/failed it) raises `FailedEventMessageNotFoundError` instead of letting Django's `DoesNotExist` leak or silently overwriting a concurrent update.
- `RetryFailedEventUseCase.execute`: raise `FailedEventMessageNotFoundError` (from the new `get_by_id` None-check) instead of the ad hoc `LookupError`.
- **Not in scope**: no changes to `FailedEventMessage`'s model fields — `status` is already the right discriminator for this model; adding `QuizActiveMixin`/`QuizSoftDeleteMixin` (is_active/is_deleted) was considered and explicitly rejected as unnecessary duplication for a dead-letter record.
- **Not in scope**: the `async_database()` decorator for `shared/` (separate change, not yet designed).

## Capabilities

No spec-level behavior changes for a well-behaved caller (a single retry still resolves or re-fails exactly as before). The only new observable behavior is under concurrency: a second concurrent retry of an already-resolved row now fails fast with a clear domain exception instead of racing a database write. This is a correctness/robustness fix to the DLQ capability introduced in `complete-eventing-use-case-layers`, not a new capability — see `skip_specs: true` in `.openspec.yaml`.

### New Capabilities
(none)

### Modified Capabilities
(none)

## Impact

- `src/shared/domain/exceptions.py` (new)
- `src/eventing/domain/exceptions.py` (new)
- `src/eventing/infrastructure/repositories/failed_event_message_repository_imp.py`
- `src/eventing/application/retry_failed_event_use_case/use_case.py`
- `tests/fixtures/eventing_fixtures.py` (`FakeFailedEventMessageRepository` needs to mirror the new status-guarded contract)
- `tests/eventing/infrastructure/test_failed_event_message_repository_imp.py`, `tests/eventing/application/retry_failed_event_use_case/test_use_case.py`
- No new dependencies. No changes to `FailedEventMessage`'s schema/migrations.
