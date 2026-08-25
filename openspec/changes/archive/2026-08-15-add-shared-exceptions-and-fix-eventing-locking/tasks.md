## 1. Shared exceptions

- [x] 1.1 Create `src/shared/domain/exceptions.py` with `DomainError` and `NotFoundError(DomainError)`

## 2. Eventing exceptions

- [x] 2.1 Create `src/eventing/domain/exceptions.py` with `FailedEventMessageNotFoundError(NotFoundError)`, taking the failed event's `id` and formatting a message with it

## 3. Repository locking fix

- [x] 3.1 `FailedEventMessageRepositoryImpl.mark_resolved`: wrap in `transaction.atomic()`, fetch via `select_for_update().filter(id=id, status=FailedEventStatus.PENDING.value).first()`, raise `FailedEventMessageNotFoundError(id)` if `None`
- [x] 3.2 `FailedEventMessageRepositoryImpl.mark_retry_failed`: same pattern
- [x] 3.3 Add `tests/eventing/infrastructure/test_failed_event_message_repository_imp.py` cases: calling `mark_resolved` twice on the same id raises `FailedEventMessageNotFoundError` the second time; same for `mark_retry_failed`; `mark_resolved`/`mark_retry_failed` on an unknown id raises `FailedEventMessageNotFoundError`

## 4. Retry use case

- [x] 4.1 `RetryFailedEventUseCase.execute`: replace the `LookupError` raised on a missing `get_by_id` result with `FailedEventMessageNotFoundError(dto.failed_event_id)`
- [x] 4.2 Update `tests/eventing/application/retry_failed_event_use_case/test_use_case.py`'s `test_execute_raises_lookup_error_for_unknown_id` to expect `FailedEventMessageNotFoundError` instead

## 5. Test double parity

- [x] 5.1 Update `FakeFailedEventMessageRepository` in `tests/fixtures/eventing_fixtures.py`: `mark_resolved`/`mark_retry_failed` raise `FailedEventMessageNotFoundError` when the row is missing or its `status` isn't `PENDING`, mirroring the real implementation's new contract

## 6. Verification

- [x] 6.1 `python manage.py check` passes
- [x] 6.2 `make test` passes with the full suite green
